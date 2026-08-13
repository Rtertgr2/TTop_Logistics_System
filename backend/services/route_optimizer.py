import math
import logging
from urllib.parse import quote
from datetime import datetime, timedelta

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from database.db import get_vehicles_from_db
from config import DEPOT_LAT, DEPOT_LNG, DEPOT_ADDRESS, SOLVE_TIMEOUT_SECONDS, MAX_ROUTE_DISTANCE_KM, MAX_STOPS_BEFORE_CLUSTER, AVG_SPEED_KMH, PRIORITY_TIME_COST_WEIGHT, PRIORITY_STOP_COST_WEIGHT
from services.distance_matrix_real import get_distance_matrix_real
from services.geo_utils import haversine_km

logger = logging.getLogger(__name__)


def _parse_time_to_minutes(time_str: str) -> int | None:
    """แปลงเวลา HH:MM เป็นนาที (ตั้งแต่ 00:00)
    
    Return: นาที (0-1440) หรือ None ถ้าไม่ถูกต้อง
    """
    if not time_str:
        return None
    
    try:
        parts = time_str.strip().split(":")
        if len(parts) != 2:
            return None
        
        hours = int(parts[0])
        minutes = int(parts[1])
        
        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            return None
        
        return hours * 60 + minutes
    except (ValueError, TypeError):
        return None


def _get_order_time_windows(orders: list[dict]) -> list[tuple[int, int]]:
    """ดึง time window จาก orders ทุกตัว
    
    Return: list of (start_minutes, end_minutes) สำหรับแต่ละ order
    ถ้าไม่มี time window ให้ใช้ default (0, 1440) = ทั้งวัน
    """
    time_windows = []
    
    for order in orders:
        start_str = order.get("time_window_start")
        end_str = order.get("time_window_end")
        
        start_minutes = _parse_time_to_minutes(start_str)
        end_minutes = _parse_time_to_minutes(end_str)
        
        # ถ้าไม่มี time window ให้ใช้ default (ทั้งวัน)
        if start_minutes is None:
            start_minutes = 0  # 00:00
        if end_minutes is None:
            end_minutes = 1440  # 24:00
        
        # ตรวจสอบความถูกต้อง
        if start_minutes >= end_minutes:
            logger.warning(f"Invalid time window for order {order.get('id')}: {start_str}-{end_str}")
            start_minutes = 0
            end_minutes = 1440
        
        time_windows.append((start_minutes, end_minutes))
    
    return time_windows


def load_vehicles() -> list[dict]:
    """โหลดข้อมูลรถจาก SQLite คัดเฉพาะ active"""
    try:
        vehicles = get_vehicles_from_db()
        active = [v for v in vehicles if v.get("active", True)]
        logger.info(f"โหลดรถจาก DB {len(active)}/{len(vehicles)} คัน")
        return active if active else vehicles
    except Exception as e:
        logger.error(f"โหลดรถจาก DB ไม่สำเร็จ: {e}")
        return []


def generate_google_maps_link(stops: list[dict], depot: dict = None) -> str:
    """สร้าง Google Maps Directions Link"""
    points = []
    if depot:
        lat = depot.get("lat", DEPOT_LAT)
        lng = depot.get("lng", DEPOT_LNG)
        points.append(f"{lat},{lng}")

    for stop in stops:
        if stop.get("lat") and stop.get("lng"):
            points.append(f"{stop['lat']},{stop['lng']}")
        elif stop.get("address"):
            points.append(quote(stop["address"]))

    if depot and len(points) > 0:
        points.append(points[0])

    if not points:
        return ""

    return "https://www.google.com/maps/dir/" + "/".join(points)


def _distance_matrix_to_int_meters(matrix: list[list[float]]) -> list[list[int]]:
    """แปลง distance matrix (km float) เป็น int (เมตร)"""
    max_int_meters = 10**9  # 1,000,000 km cap — ป้องกัน OverflowError จาก inf/NaN
    return [
        [max_int_meters if cell == float("inf") or cell != cell else int(cell * 1000) for cell in row]
        for row in matrix
    ]


def _make_stop_fields(order: dict) -> dict:
    """สร้าง fields สำหรับ stop dict จาก order"""
    return {
        "id": order.get("id"),
        "customer": order.get("customer", ""),
        "address": order.get("address", ""),
        "weight": float(order.get("weight") or 0),
        "lat": order.get("lat"),
        "lng": order.get("lng"),
        "raw_lat": order.get("raw_lat", order.get("lat")),
        "raw_lng": order.get("raw_lng", order.get("lng")),
        "verified_lat": order.get("verified_lat", order.get("lat")),
        "verified_lng": order.get("verified_lng", order.get("lng")),
        "confidence_score": order.get("confidence_score", 30.0),
        "geocode_provider": order.get("geocode_provider", "google"),
        "is_verified": bool(order.get("is_verified", False)),
        "order_number": order.get("order_number"),
        "zone": order.get("zone", ""),
        "products": order.get("products", []),
    }


# ─── 1.4.5 Clustering ──────────────────────────────────────────────

def _kmeans_cluster(points: list[dict], k: int, depot_lat: float, depot_lng: float) -> list[list[int]]:
    """K-means clustering — คืน list of clusters (แต่ละ cluster = list of indices)"""
    n = len(points)
    if k >= n:
        return [[i] for i in range(n)]

    # 初始化 centroids = สุ่ม k จุดแรก
    centroids_lat = [points[i]["lat"] for i in range(k)]
    centroids_lng = [points[i]["lng"] for i in range(k)]

    labels = [0] * n

    for _ in range(20):  # max 20 iterations
        # กำหนด cluster ให้แต่ละจุด
        changed = False
        for i, p in enumerate(points):
            best_c = 0
            best_d = float("inf")
            for c in range(k):
                d = haversine_km(p["lat"], p["lng"], centroids_lat[c], centroids_lng[c])
                if d < best_d:
                    best_d = d
                    best_c = c
            if labels[i] != best_c:
                labels[i] = best_c
                changed = True

        if not changed:
            break

        # Update centroids
        sums_lat = [0.0] * k
        sums_lng = [0.0] * k
        counts = [0] * k
        for i, p in enumerate(points):
            c = labels[i]
            sums_lat[c] += p["lat"]
            sums_lng[c] += p["lng"]
            counts[c] += 1

        for c in range(k):
            if counts[c] > 0:
                centroids_lat[c] = sums_lat[c] / counts[c]
                centroids_lng[c] = sums_lng[c] / counts[c]

    # จัดกลุ่ม indices
    clusters = [[] for _ in range(k)]
    for i, c in enumerate(labels):
        clusters[c].append(i)

    # ลบ cluster ว่างออก
    return [cl for cl in clusters if cl]


def _cluster_orders(orders: list[dict], depot_lat: float, depot_lng: float) -> list[list[dict]]:
    """แบ่ง orders เป็น clusters ตามระยะทาง (ใช้เมื่อ > MAX_STOPS_BEFORE_CLUSTER)"""
    n = len(orders)
    if n <= MAX_STOPS_BEFORE_CLUSTER:
        return [orders]

    # จำนวน cluster = ceil(n / MAX_STOPS_BEFORE_CLUSTER)
    k = math.ceil(n / MAX_STOPS_BEFORE_CLUSTER)

    # เตรียม points (skip orders ที่ไม่มี lat/lng)
    valid = []
    valid_indices = []
    for i, o in enumerate(orders):
        lat = o.get("lat", depot_lat)
        lng = o.get("lng", depot_lng)
        if lat and lng:
            valid.append({"lat": lat, "lng": lng})
            valid_indices.append(i)

    if not valid:
        return [orders]

    clusters_idx = _kmeans_cluster(valid, k, depot_lat, depot_lng)

    # แปลงกลับเป็น orders
    result = []
    for cl in clusters_idx:
        cluster_orders = [orders[valid_indices[i]] for i in cl]
        result.append(cluster_orders)

    logger.info(f"Clustered {n} orders into {len(result)} zones (max {MAX_STOPS_BEFORE_CLUSTER} stops/zone)")
    return result


# ─── 1.4.6 Validate Constraints ─────────────────────────────────────

def _validate_inputs(orders: list[dict], vehicles: list[dict]) -> list[str]:
    """ตรวจสอบ inputs ก่อนคำนวณ — คืน list of warnings"""
    warnings = []

    if not orders:
        warnings.append("ไม่มี orders")
        return warnings

    if not vehicles:
        warnings.append("ไม่มี vehicles")
        return warnings

    total_weight = sum(float(o.get("weight") or 0) for o in orders)
    total_capacity = sum(float(v.get("capacity", 3750)) for v in vehicles)

    if total_capacity > 0 and total_weight / total_capacity > 1.0:
        warnings.append(f"น้ำหนักรวม ({total_weight:.0f} kg) เกินความจุรถรวม ({total_capacity:.0f} kg)")

    for i, o in enumerate(orders):
        w = float(o.get("weight") or 0)
        if w < 0:
            warnings.append(f"Order #{i+1} มีน้ำหนักติดลบ ({w})")
        elif w == 0:
            warnings.append(f"Order #{i+1} ไม่มีน้ำหนัก (ใช้ 0 kg)")

    orders_without_coords = [i for i, o in enumerate(orders) if not o.get("lat") or not o.get("lng")]
    if orders_without_coords:
        warnings.append(f"{len(orders_without_coords)} orders ไม่มีพิกัด (จะใช้ Haversine จาก depot)")

    return warnings


# ─── 1.4.7 ETA Calculation ──────────────────────────────────────────

def _calculate_eta(stops: list[dict], distance_matrix_int: list[list[int]], depot_lat: float, depot_lng: float, start_hour: int = 8) -> list[dict]:
    """คำนวณ ETA ทุกจุด — สมมติ depot เป็นจุดเริ่มต้น, เริ่มจาก start_hour (default 08:00)"""
    if not stops:
        return stops

    now = datetime.now()
    start_time = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    # ถ้าเลย start_hour แล้ว ให้ใช้วันพรุ่งนี้
    if now.hour >= start_hour:
        start_time += timedelta(days=1)
    cumulative_minutes = 0.0

    prev_lat, prev_lng = depot_lat, depot_lng

    for i, stop in enumerate(stops):
        # คำนวณระยะทางจากจุดก่อนหน้า
        s_lat = stop.get("lat", depot_lat)
        s_lng = stop.get("lng", depot_lng)
        dist_km = haversine_km(prev_lat, prev_lng, s_lat, s_lng)

        # เวลาเดินทาง (นาที) = distance / speed * 60
        travel_minutes = (dist_km / AVG_SPEED_KMH) * 60 if dist_km > 0 else 0

        # เวลาหยุด (ค่าเริ่มต้น 5 นาทีต่อจุด)
        stop_minutes = 5

        cumulative_minutes += travel_minutes + stop_minutes

        eta = start_time + timedelta(minutes=cumulative_minutes)
        stop["eta"] = eta.strftime("%H:%M")
        stop["eta_minutes"] = round(cumulative_minutes, 1)

        prev_lat, prev_lng = s_lat, s_lng

    return stops


# ─── Demand Mode Selection ───────────────────────────────────────────

def _choose_demand_mode(orders: list[dict], vehicles: list[dict]) -> tuple[str, list[int], list[int]]:
    """เลือก demand mode: 'weight' หรือ 'stop_count'

    ใช้ weight-based เป็นหลัก — solver จะกระจายตาม distance โดยอัตโนมัติ
    ใช้ stop_count ถ้าน้ำหนักรวม = 0 (ทุก order ไม่มี weight)
    """
    total_weight = sum(float(o.get("weight") or 0) for o in orders)

    if total_weight > 0:
        v_caps = [int(float(v.get("capacity", 3750))) for v in vehicles]
        o_demands = [0] + [int(float(o.get("weight") or 0)) for o in orders]
        return "weight", v_caps, o_demands
    else:
        avg_stops = math.ceil(len(orders) / len(vehicles)) if vehicles else len(orders)
        v_caps = []
        for v in vehicles:
            max_stops = v.get("max_stops", 0)
            if max_stops and max_stops > 0:
                v_caps.append(int(max_stops))
            else:
                v_caps.append(int(avg_stops * 1.5) + 1)
        o_demands = [0] + [1] * len(orders)
        return "stop_count", v_caps, o_demands


# ─── OR-Tools Solver ─────────────────────────────────────────────────

def _solve_vrp(
    distance_matrix_int: list[list[int]],
    num_vehicles: int,
    vehicle_capacities: list[int],
    order_demands: list[int],
    depot_index: int = 0,
    time_windows: list[tuple[int, int]] = None,
    service_time_minutes: int = 5,
) -> dict | None:
    """แก้ CVRPTW ด้วย OR-Tools
    
    Args:
        distance_matrix_int: distance matrix (เมตร)
        num_vehicles: จำนวนรถ
        vehicle_capacities: capacity แต่ละรถ
        order_demands: demand แต่ละจุด (depot = 0)
        depot_index: index ของ depot
        time_windows: list of (start_minutes, end_minutes) สำหรับแต่ละจุด
        service_time_minutes: เวลาหยุดแต่ละจุด (นาที)
    """

    n = len(distance_matrix_int)

    manager = pywrapcp.RoutingIndexManager(n, num_vehicles, depot_index)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix_int[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)

    # ── Combined arc-cost objective (priority order) ──────────────────
    # Priority 1 (weight) = HARD capacity constraint (handled by Capacity dimension below).
    # Priority 2 (time & distance) = dominant term in the cost.
    # Priority 3 (number of stops) = small per-stop penalty (tertiary).
    # cost = distance_m + TIME_COST_WEIGHT * travel_minutes + STOP_COST_WEIGHT
    def cost_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        dist_m = distance_matrix_int[from_node][to_node]
        travel_min = dist_m / (AVG_SPEED_KMH * 1000 / 60)
        # Penalize each customer stop once (on its outgoing edge) → minimizes #stops (tier 3)
        stop_penalty = PRIORITY_STOP_COST_WEIGHT if from_node != depot_index else 0
        return int(dist_m + PRIORITY_TIME_COST_WEIGHT * travel_min + stop_penalty)

    cost_callback_index = routing.RegisterTransitCallback(cost_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(cost_callback_index)

    def demand_callback(from_index):
        from_node = manager.IndexToNode(from_index)
        return order_demands[from_node]

    demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
    routing.AddDimensionWithVehicleCapacity(
        demand_callback_index,
        0,
        vehicle_capacities,
        True,
        "Capacity",
    )

    max_dist_meters = MAX_ROUTE_DISTANCE_KM * 1000
    routing.AddDimension(
        transit_callback_index,
        0,
        max_dist_meters,
        True,
        "Distance",
    )

    # Time Window dimension (Sprint 2.2)
    if time_windows and len(time_windows) == n:
        # สร้าง time callback: เวลาเดินทาง + เวลาหยุด
        def time_callback(from_index, to_index):
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            # เวลาเดินทาง (นาที) = ระยะทาง (เมตร) / ความเร็ว (เมตร/นาที)
            travel_time = distance_matrix_int[from_node][to_node] / (AVG_SPEED_KMH * 1000 / 60)
            # เวลาหยุด (เฉพาะจุดที่ไม่ใช่ depot)
            service = service_time_minutes if from_node != depot_index else 0
            return int(travel_time + service)

        time_callback_index = routing.RegisterTransitCallback(time_callback)
        
        # กำหนด time dimension
        max_time = 1440  # 24 ชั่วโมง = 1440 นาที
        routing.AddDimension(
            time_callback_index,
            max_time,  # allow waiting time
            max_time,  # maximum time per vehicle
            False,     # don't force start cumulative to zero
            "Time",
        )
        
        time_dimension = routing.GetDimensionOrDie("Time")
        
        # ตั้ง time window สำหรับแต่ละจุด
        for location_idx, (start, end) in enumerate(time_windows):
            index = manager.NodeToIndex(location_idx)
            time_dimension.CumulVar(index).SetRange(start, end)
        
        # ตั้ง time window สำหรับ depot (เริ่ม 08:00 - 18:00)
        for vehicle_idx in range(num_vehicles):
            start_index = routing.Start(vehicle_idx)
            end_index = routing.End(vehicle_idx)
            time_dimension.CumulVar(start_index).SetRange(0, 1440)
            time_dimension.CumulVar(end_index).SetRange(0, 1440)
        
        logger.info(f"Time Window dimension added: {len(time_windows)} locations with time windows")
    else:
        logger.info("No time windows specified — solving CVRP (without time windows)")

    # Fixed cost per vehicle:  penalize using more vehicles (prefer fewer vehicles)
    # ค่านี้ทำให้ solver พยายามใช้รถน้อยลงเพื่อประหยัดค่าใช้จ่าย
    routing.SetFixedCostOfAllVehicles(100000)

    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.CHRISTOFIDES
    )
    search_parameters.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_parameters.time_limit.seconds = SOLVE_TIMEOUT_SECONDS

    solution = routing.SolveWithParameters(search_parameters)

    if solution is None:
        return None

    return {
        "solution": solution,
        "routing": routing,
        "manager": manager,
        "objective_value": solution.ObjectiveValue(),
    }


def _extract_routes(
    result: dict,
    orders: list[dict],
    vehicles: list[dict],
    distance_matrix_int: list[list[int]],
    depot_lat: float = DEPOT_LAT,
    depot_lng: float = DEPOT_LNG,
) -> list[dict]:
    """แปลง OR-Tools solution เป็น list of route dicts พร้อม ETA"""
    solution = result["solution"]
    routing = result["routing"]
    manager = result["manager"]

    routes = []

    for vehicle_idx in range(len(vehicles)):
        vehicle = vehicles[vehicle_idx]
        index = routing.Start(vehicle_idx)
        stops = []
        total_distance_m = 0

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != 0:
                order = orders[node - 1]
                stops.append(_make_stop_fields(order))

            prev_index = index
            index = solution.Value(routing.NextVar(index))

            from_node = manager.IndexToNode(prev_index)
            to_node = manager.IndexToNode(index)
            total_distance_m += distance_matrix_int[from_node][to_node]

        if stops:
            total_weight = round(sum(s["weight"] for s in stops), 2)
            v_capacity = float(vehicle.get("capacity", 3750))

            # 1.4.7 — คำนวณ ETA
            stops = _calculate_eta(stops, distance_matrix_int, depot_lat, depot_lng)

            depot = {
                "lat": depot_lat,
                "lng": depot_lng,
                "address": DEPOT_ADDRESS,
            }

            maps_link = generate_google_maps_link(stops, depot)

            routes.append({
                "vehicle_id": vehicle.get("id", vehicle_idx + 1),
                "plate": vehicle.get("plate", ""),
                "driver": vehicle.get("driver", ""),
                "name": vehicle.get("name", f"รถคันที่ {vehicle.get('id', vehicle_idx + 1)}"),
                "capacity": v_capacity,
                "stops": stops,
                "total_weight": total_weight,
                "total_distance_km": round(total_distance_m / 1000, 2),
                "google_maps_link": maps_link,
                "depot": depot,
            })

    return routes


def _fallback_sweep(
    orders: list[dict],
    vehicles: list[dict],
    depot_lat: float,
    depot_lng: float,
) -> list[dict]:
    """Fallback: Sweep + Nearest Neighbor TSP ถ้า OR-Tools ล้มเหลว"""

    for order in orders:
        lat = order.get("lat", depot_lat)
        lng = order.get("lng", depot_lng)
        dlat = lat - depot_lat
        dlng = lng - depot_lng
        order["_angle"] = math.atan2(dlng, dlat)
        order["_dist"] = math.sqrt(dlat**2 + dlng**2)

    sorted_orders = sorted(orders, key=lambda x: x.get("_angle", 0))
    num_vehicles = len(vehicles)
    target = math.ceil(len(sorted_orders) / num_vehicles)

    routes = []
    warnings = []
    cursor = 0

    for v_idx, vehicle in enumerate(vehicles):
        if cursor >= len(sorted_orders):
            break

        v_capacity = float(vehicle.get("capacity", 3750))
        current_weight = 0.0
        raw = []

        max_pts = target if v_idx < num_vehicles - 1 else (len(sorted_orders) - cursor)

        while cursor < len(sorted_orders) and len(raw) < max_pts:
            order = sorted_orders[cursor]
            w = float(order.get("weight") or 0)
            if current_weight + w <= v_capacity or not raw:
                raw.append(order)
                current_weight += w
                cursor += 1
            else:
                if v_idx == num_vehicles - 1:
                    # รถคันสุดท้าย: รับ order ที่เหลือแม้เกินความจุ (ป้องกันตกหล่น silently)
                    raw.append(order)
                    current_weight += w
                    cursor += 1
                else:
                    break

        if raw:
            # แจ้งเตือนรถคันสุดท้ายเกินความจุ (รวมเป็นข้อความเดียว)
            if v_idx == num_vehicles - 1 and current_weight > v_capacity:
                warnings.append(
                    f"รถ {vehicle.get('name', 'คันที่ ' + str(v_idx + 1))} รับออเดอร์เกินความจุ "
                    f"({current_weight:.0f}/{v_capacity:.0f} kg) — กรุณาเพิ่มรถหรือลดออเดอร์"
                )
            ordered_stops = _tsp_nearest_neighbor(raw, depot_lat, depot_lng)
            formatted = [_make_stop_fields(s) for s in ordered_stops]

            # 1.4.7 — คำนวณ ETA สำหรับ fallback routes ด้วย
            dummy_dm = [[0] * (len(formatted) + 1) for _ in range(len(formatted) + 1)]
            all_pts = [{"lat": depot_lat, "lng": depot_lng}] + formatted
            for i in range(len(all_pts)):
                for j in range(len(all_pts)):
                    if i != j:
                        dummy_dm[i][j] = int(haversine_km(
                            all_pts[i].get("lat", depot_lat), all_pts[i].get("lng", depot_lng),
                            all_pts[j].get("lat", depot_lat), all_pts[j].get("lng", depot_lng),
                        ) * 1000)
            formatted = _calculate_eta(formatted, dummy_dm, depot_lat, depot_lng)

            depot = {
                "lat": depot_lat,
                "lng": depot_lng,
                "address": DEPOT_ADDRESS,
            }

            maps_link = generate_google_maps_link(formatted, depot)

            # Calculate total distance from dummy_dm
            total_dist_km = 0
            prev_idx = 0  # depot
            for stop_idx in range(1, len(formatted) + 1):
                total_dist_km += dummy_dm[prev_idx][stop_idx] / 1000
                prev_idx = stop_idx
            total_dist_km += dummy_dm[prev_idx][0] / 1000  # return to depot

            routes.append({
                "vehicle_id": vehicle.get("id", v_idx + 1),
                "plate": vehicle.get("plate", ""),
                "driver": vehicle.get("driver", ""),
                "name": vehicle.get("name", f"รถคันที่ {vehicle.get('id', v_idx + 1)}"),
                "capacity": v_capacity,
                "stops": formatted,
                "total_weight": round(current_weight, 2),
                "total_distance_km": round(total_dist_km, 2),
                "google_maps_link": maps_link,
                "depot": depot,
            })

    return {"routes": routes, "warnings": warnings}


def _tsp_nearest_neighbor(stops: list[dict], depot_lat: float, depot_lng: float) -> list[dict]:
    """จัดลำดับจุดส่งตาม Nearest Neighbor TSP"""
    if len(stops) <= 1:
        return stops

    curr_lat, curr_lng = depot_lat, depot_lng
    unvisited = list(stops)
    ordered = []

    while unvisited:
        best_idx = 0
        best_dist = float("inf")
        for idx, stop in enumerate(unvisited):
            s_lat = stop.get("lat", depot_lat)
            s_lng = stop.get("lng", depot_lng)
            dist = haversine_km(curr_lat, curr_lng, s_lat, s_lng)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx

        nxt = unvisited.pop(best_idx)
        ordered.append(nxt)
        curr_lat = nxt.get("lat", depot_lat)
        curr_lng = nxt.get("lng", depot_lng)

    return ordered


def _rebalance_routes(
    routes: list[dict],
    orders: list[dict],
    vehicles: list[dict],
    depot_lat: float,
    depot_lng: float,
) -> list[dict]:
    """ตรวจสอบความสมดุล — ย้าย stop จาก overloaded ไป underloaded"""
    if not routes or len(routes) <= 1:
        return routes

    total_stops = sum(len(r["stops"]) for r in routes)
    if total_stops == 0:
        return routes

    avg = total_stops / len(routes)
    min_acceptable = max(1, avg * 0.3)

    active_route_ids = {r["vehicle_id"] for r in routes}
    for v in vehicles:
        if v.get("active", True) and v.get("id") not in active_route_ids:
            routes.append({
                "vehicle_id": v.get("id"),
                "plate": v.get("plate", ""),
                "driver": v.get("driver", ""),
                "name": v.get("name", f"รถคันที่ {v.get('id')}"),
                "capacity": float(v.get("capacity", 3750)),
                "stops": [],
                "total_weight": 0,
                "total_distance_km": 0,
                "google_maps_link": "",
            })

    total_stops = sum(len(r["stops"]) for r in routes)
    avg = total_stops / len(routes)
    min_acceptable = max(1, avg * 0.3)

    underloaded = [r for r in routes if len(r["stops"]) < min_acceptable]
    overloaded = [r for r in routes if len(r["stops"]) > avg * 1.2]

    if underloaded:
        logger.info(f"Rebalancing: {len(underloaded)} underloaded (avg={avg:.1f}, min={min_acceptable:.1f})")

        for under in underloaded:
            if not overloaded:
                overloaded = [r for r in routes if r is not under and len(r["stops"]) > 1]
                if not overloaded:
                    break

            best_stop = None
            best_source = None
            best_dist = float("inf")

            for over in overloaded:
                if len(over["stops"]) <= 1:
                    continue
                for stop in over["stops"]:
                    s_lat = stop.get("lat", depot_lat)
                    s_lng = stop.get("lng", depot_lng)
                    if under["stops"]:
                        ref_lat = under["stops"][0].get("lat", depot_lat)
                        ref_lng = under["stops"][0].get("lng", depot_lng)
                    else:
                        ref_lat = depot_lat
                        ref_lng = depot_lng
                    dist = haversine_km(ref_lat, ref_lng, s_lat, s_lng)
                    if dist < best_dist:
                        best_dist = dist
                        best_stop = stop
                        best_source = over

            if best_stop and best_source:
                best_source["stops"].remove(best_stop)
                under["stops"].append(best_stop)
                under["total_weight"] = round(sum(s.get("weight", 0) for s in under["stops"]), 2)
                best_source["total_weight"] = round(sum(s.get("weight", 0) for s in best_source["stops"]), 2)
                under["google_maps_link"] = generate_google_maps_link(under["stops"], None)
                best_source["google_maps_link"] = generate_google_maps_link(best_source["stops"], None)
                logger.info(f"Moved stop '{best_stop.get('customer', '')[:20]}' from vehicle {best_source['vehicle_id']} -> {under['vehicle_id']}")

    routes = [r for r in routes if len(r["stops"]) > 0]

    # ── Weight-based rebalancing ──────────────────────────────────────
    # ย้าย stops จากคันที่น้ำหนักเกินไปคันที่ยังมีที่
    MAX_WEIGHT_ITERATIONS = 100
    for _iter in range(MAX_WEIGHT_ITERATIONS):
        # คำนวณน้ำหนักปัจจุบันของทุกคัน
        for r in routes:
            r["total_weight"] = round(sum(s.get("weight", 0) for s in r["stops"]), 2)

        # หาคันที่เกิน capacity
        overloaded = [r for r in routes if r["total_weight"] > r.get("capacity", 3750)]
        if not overloaded:
            break

        # หาคันที่มีที่เหลือ
        available = [r for r in routes if r["total_weight"] < r.get("capacity", 3750) * 0.98]
        if not available:
            logger.warning(f"Weight rebalance iter {_iter}: no available trucks")
            break

        logger.info(
            f"Weight rebalance iter {_iter}: {len(overloaded)} overloaded, {len(available)} available. "
            f"Trucks: {[(r.get('vehicle_id'), r['total_weight'], r.get('capacity', 3750)) for r in routes]}"
        )

        moved = False
        for over in overloaded:
            if not over["stops"]:
                continue
            # เรียง stops จากเบาไปหนัก เพื่อย้ายตัวที่เบาสุดที่ย้ายได้
            sorted_stops = sorted(over["stops"], key=lambda s: s.get("weight", 0))
            for stop_candidate in sorted_stops:
                # หาคันที่รับได้และใกล้ที่สุด
                best_target = None
                best_dist = float("inf")
                for target in available:
                    if target is over:
                        continue
                    remaining = target.get("capacity", 3750) - target["total_weight"]
                    if stop_candidate.get("weight", 0) > remaining:
                        continue
                    # คำนวณระยะทางจาก stop สุดท้ายของ target
                    if target["stops"]:
                        ref_lat = target["stops"][-1].get("lat", depot_lat)
                        ref_lng = target["stops"][-1].get("lng", depot_lng)
                    else:
                        ref_lat, ref_lng = depot_lat, depot_lng
                    s_lat = stop_candidate.get("lat", depot_lat)
                    s_lng = stop_candidate.get("lng", depot_lng)
                    dist = haversine_km(ref_lat, ref_lng, s_lat, s_lng)
                    if dist < best_dist:
                        best_dist = dist
                        best_target = target

                if best_target:
                    over["stops"].remove(stop_candidate)
                    best_target["stops"].append(stop_candidate)
                    over["total_weight"] = round(sum(s.get("weight", 0) for s in over["stops"]), 2)
                    best_target["total_weight"] = round(sum(s.get("weight", 0) for s in best_target["stops"]), 2)
                    over["google_maps_link"] = generate_google_maps_link(over["stops"], None)
                    best_target["google_maps_link"] = generate_google_maps_link(best_target["stops"], None)
                    moved = True
                    logger.info(
                        f"Weight rebalance: moved '{stop_candidate.get('customer', '')[:20]}' "
                        f"({stop_candidate.get('weight', 0)} kg) from {over.get('vehicle_id')} -> {best_target.get('vehicle_id')}"
                    )
                    break  # restart outer loop

        if not moved:
            logger.warning(f"Weight rebalance: no moves possible after iter {_iter}")
            break

    return routes


# ─── Multi-day Overflow Splitting ────────────────────────────────────

def _split_orders_by_capacity(
    orders: list[dict], total_capacity: float
) -> tuple[list[dict], list[dict]]:
    """แบ่งออเดอร์เป็น 'ส่งวันนี้' กับ 'ส่งวันถัดไป' ตามน้ำหนัก

    เก็บออเดอร์ที่น้ำหนักรวม <= total_capacity ไว้ส่งวันนี้
    ที่เหลือ → overflow (ส่งวันถัดไป)
    เรียงลำดับตามน้ำหนักจากน้อยไปมาก เพื่อเก็บจำนวน order สูงสุดไว้วันนี้
    """
    # เรียงตามน้ำหนักน้อย → มาก (เก็บหลาย order ได้มากกว่า)
    sorted_orders = sorted(orders, key=lambda o: float(o.get("weight") or 0))

    today = []
    overflow = []
    cumulative = 0.0

    for o in sorted_orders:
        w = float(o.get("weight") or 0)
        if cumulative + w <= total_capacity:
            today.append(o)
            cumulative += w
        else:
            overflow.append(o)

    return today, overflow


# ─── Main Entry Point ────────────────────────────────────────────────

def optimize_routes(
    orders: list[dict],
    vehicles: list[dict] = None,
    depot: dict = None,
) -> dict:
    """แก้ CVRPTW ด้วย OR-Tools

    ขั้นตอน:
    1. Validate inputs
    2. ถ้า >200 stops → cluster เป็น zone ก่อน
    3. สร้าง distance matrix (depot = index 0)
    4. เลือก demand mode: weight หรือ stop_count
    5. แก้ VRP ด้วย OR-Tools + Christofides + GLS
    6. คำนวณ ETA ทุกจุด
    7. Rebalance routes
    8. Fallback เป็น Sweep + Nearest Neighbor ถ้าล้มเหลว

    คืนค่า dict: { "routes": [...], "warnings": [...], "clustered": bool }
    """
    if not orders:
        return {
            "routes": [],
            "warnings": [],
            "clustered": False,
            "deferred_orders": [],
            "deferred_weight": 0,
            "deferred_count": 0,
        }

    if vehicles is None:
        vehicles = load_vehicles()

    num_vehicles = len(vehicles)
    if num_vehicles == 0:
        logger.warning("ไม่มีรถที่เปิดใช้งาน")
        return {
            "routes": [],
            "warnings": ["ไม่มีรถที่เปิดใช้งาน"],
            "clustered": False,
            "deferred_orders": [],
            "deferred_weight": 0,
            "deferred_count": 0,
        }

    depot_lat = depot.get("lat", DEPOT_LAT) if depot else DEPOT_LAT
    depot_lng = depot.get("lng", DEPOT_LNG) if depot else DEPOT_LNG

    # 1. Validate inputs
    warnings = _validate_inputs(orders, vehicles)
    if warnings:
        logger.warning(f"Validation warnings: {warnings}")

    # 1.5 ตรวจว่าน้ำหนักเกิน capacity หรือไม่ → แบ่งส่งวันถัดไป
    total_weight = sum(float(o.get("weight") or 0) for o in orders)
    total_capacity = sum(float(v.get("capacity", 3750)) for v in vehicles)
    deferred_orders = []

    if total_weight > total_capacity and total_capacity > 0:
        today_orders, deferred_orders = _split_orders_by_capacity(orders, total_capacity)
        overflow_weight = sum(float(o.get("weight") or 0) for o in deferred_orders)
        overflow_count = len(deferred_orders)
        logger.warning(
            f"น้ำหนักเกิน! ส่งวันนี้ {len(today_orders)} รายการ, "
            f"เลื่อนส่งวันถัดไป {overflow_count} รายการ ({overflow_weight:.0f} kg)"
        )
        warnings.append(
            f"น้ำหนักรวม ({total_weight:.0f} kg) เกินความจุรถ ({total_capacity:.0f} kg) — "
            f"ออเดอร์ {overflow_count} รายการ ({overflow_weight:.0f} kg) จะถูกส่งในวันถัดไป"
        )
        orders = today_orders  # ใช้เฉพาะ orders ที่ส่งวันนี้

    # 2. Clustering — ถ้า orders > MAX_STOPS_BEFORE_CLUSTER
    if len(orders) > MAX_STOPS_BEFORE_CLUSTER:
        clusters = _cluster_orders(orders, depot_lat, depot_lng)
        all_routes = []

        for cluster_idx, cluster_orders in enumerate(clusters):
            logger.info(f"Solving cluster {cluster_idx + 1}/{len(clusters)}: {len(cluster_orders)} orders")
            cluster_result = _solve_cluster(cluster_orders, vehicles, depot_lat, depot_lng)
            all_routes.extend(cluster_result["routes"])
            warnings.extend(cluster_result["warnings"])

        logger.info(f"Clustered VRP เสร็จ: {len(all_routes)} routes จาก {len(clusters)} clusters")
        deferred_weight = sum(float(o.get("weight") or 0) for o in deferred_orders)
        return {
            "routes": all_routes,
            "warnings": warnings,
            "clustered": True,
            "deferred_orders": deferred_orders,
            "deferred_weight": round(deferred_weight, 2),
            "deferred_count": len(deferred_orders),
        }

    # 3-8. แก้ VRP ปกติ (ไม่ cluster)
    result = _solve_cluster(orders, vehicles, depot_lat, depot_lng)
    warnings.extend(result["warnings"])
    deferred_weight = sum(float(o.get("weight") or 0) for o in deferred_orders)
    return {
        "routes": result["routes"],
        "warnings": warnings,
        "clustered": False,
        "deferred_orders": deferred_orders,
        "deferred_weight": round(deferred_weight, 2),
        "deferred_count": len(deferred_orders),
    }


def _solve_cluster(
    orders: list[dict],
    vehicles: list[dict],
    depot_lat: float,
    depot_lng: float,
) -> dict:
    """แก้ VRP สำหรับ cluster เดียว (หรือทั้งหมดถ้าไม่ cluster)"""
    warnings = []

    # Distance matrix - ใช้ Google Distance Matrix API (Sprint 2.3)
    depot = {"lat": depot_lat, "lng": depot_lng}
    matrix = get_distance_matrix_real(orders, depot)
    
    # แปลงเป็น int (เมตร) สำหรับ OR-Tools
    dm_int = _distance_matrix_to_int_meters(matrix)

    demand_mode, vehicle_capacities, order_demands = _choose_demand_mode(orders, vehicles)
    logger.info(f"Demand mode: {demand_mode} | vehicles: {len(vehicles)} | orders: {len(orders)} | timeout: {SOLVE_TIMEOUT_SECONDS}s")

    # ดึง time windows จาก orders (Sprint 2.2)
    time_windows = _get_order_time_windows(orders)
    # เพิ่ม depot time window (00:00 - 24:00)
    time_windows_with_depot = [(0, 1440)] + time_windows

    result = _solve_vrp(
        distance_matrix_int=dm_int,
        num_vehicles=len(vehicles),
        vehicle_capacities=vehicle_capacities,
        order_demands=order_demands,
        depot_index=0,
        time_windows=time_windows_with_depot,
    )

    if result is not None:
        routes = _extract_routes(result, orders, vehicles, dm_int, depot_lat, depot_lng)
        total_stops = sum(len(r["stops"]) for r in routes)
        total_obj = result["objective_value"]
        logger.info(f"OR-Tools สำเร็จ: {len(routes)} routes, {total_stops} stops, objective={total_obj}")

        routes = _rebalance_routes(routes, orders, vehicles, depot_lat, depot_lng)
        return {"routes": routes, "warnings": warnings}

    # Fallback
    logger.warning("OR-Tools ล้มเหลว — ใช้ Sweep + Nearest Neighbor")
    fallback_result = _fallback_sweep(orders, vehicles, depot_lat, depot_lng)
    routes = fallback_result["routes"]
    warnings.extend(fallback_result["warnings"])
    total_stops = sum(len(r["stops"]) for r in routes)
    logger.info(f"Fallback: {len(routes)} routes, {total_stops} stops")
    routes = _rebalance_routes(routes, orders, vehicles, depot_lat, depot_lng)
    return {"routes": routes, "warnings": warnings}
