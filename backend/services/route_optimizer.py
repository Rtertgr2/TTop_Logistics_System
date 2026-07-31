import math
import logging
from urllib.parse import quote

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from database.db import get_vehicles_from_db

logger = logging.getLogger(__name__)

# Timeouts
SOLVE_TIMEOUT_SECONDS = 30


def load_vehicles() -> list[dict]:
    """โหลดข้อมูลรถจาก SQLite Database พร้อมคัดเฉพาะคันที่เปิดใช้งาน (active: true)"""
    try:
        vehicles = get_vehicles_from_db()
        active_vehicles = [v for v in vehicles if v.get("active", True)]
        logger.info(f"โหลดข้อมูลรถจาก SQLite DB {len(active_vehicles)}/{len(vehicles)} คันสำเร็จ")
        return active_vehicles if active_vehicles else vehicles
    except Exception as e:
        logger.error(f"ไม่สามารถโหลดข้อมูลรถจาก SQLite DB: {e}")
        return [
            {"id": 1, "name": "รถคันที่ 1 (รถใหญ่ 3.75 ตัน)", "plate": "กข 1234", "capacity": 3750, "driver": "สมชาย", "active": True},
            {"id": 2, "name": "รถคันที่ 2 (รถกลาง 1.8 - 1.9 ตัน)", "plate": "กข 5678", "capacity": 1900, "driver": "สมศักดิ์", "active": True},
            {"id": 3, "name": "รถคันที่ 3 (รถกลาง 1.95 - 2.24 ตัน)", "plate": "กข 9012", "capacity": 2240, "driver": "สมบูรณ์", "active": True},
            {"id": 4, "name": "รถคันที่ 4 (รถใหญ่ 3.75 ตัน)", "plate": "กข 3456", "capacity": 3750, "driver": "สมเดช", "active": True},
        ]


def generate_google_maps_link(stops: list[dict], depot: dict = None) -> str:
    """สร้าง Google Maps Directions Link จาก stops"""
    points = []
    if depot:
        lat = depot.get("lat", 13.781882)
        lng = depot.get("lng", 100.425041)
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


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """คำนวณระยะทาง Haversine (km) ระหว่าง 2 จุด"""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def _distance_matrix_to_int_km(matrix: list[list[float]]) -> list[list[int]]:
    """แปลง distance matrix (km float) เป็น int (เมตร) สำหรับ OR-Tools"""
    return [[int(cell * 1000) for cell in row] for row in matrix]


def _solve_vrp(
    distance_matrix_int: list[list[int]],
    num_vehicles: int,
    vehicle_capacities: list[int],
    order_demands: list[int],
    depot_index: int = 0,
) -> dict | None:
    """แก้ปัญหา CVRPTW ด้วย OR-Tools"""

    n = len(distance_matrix_int)

    manager = pywrapcp.RoutingIndexManager(n, num_vehicles, depot_index)
    routing = pywrapcp.RoutingModel(manager)

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return distance_matrix_int[from_node][to_node]

    transit_callback_index = routing.RegisterTransitCallback(distance_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

    # Capacity constraint
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

    # Distance limit per vehicle (optional, 500 km default)
    routing.AddDimension(
        transit_callback_index,
        0,
        500000,
        True,
        "Distance",
    )

    # Search parameters
    search_parameters = pywrapcp.DefaultRoutingSearchParameters()
    search_parameters.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
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
    }


def _extract_routes(
    result: dict,
    orders: list[dict],
    vehicles: list[dict],
) -> list[dict]:
    """แปลง OR-Tools solution เป็น list of route dicts"""
    solution = result["solution"]
    routing = result["routing"]
    manager = result["manager"]

    routes = []

    for vehicle_idx in range(len(vehicles)):
        vehicle = vehicles[vehicle_idx]
        index = routing.Start(vehicle_idx)
        stops = []
        total_distance = 0
        total_weight = 0

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != 0:  # Skip depot
                order = orders[node - 1]
                weight = float(order.get("weight", 0))
                total_weight += weight
                stops.append({
                    "id": order.get("id"),
                    "customer": order.get("customer", ""),
                    "address": order.get("address", ""),
                    "weight": weight,
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
                })

            prev_index = index
            index = solution.Value(routing.NextVar(index))
            total_distance += routing.GetArcCostForVehicle(prev_index, index, vehicle_idx)

        if stops:
            v_capacity = float(vehicle.get("capacity", 3750))
            maps_link = generate_google_maps_link(stops, None)

            routes.append({
                "vehicle_id": vehicle.get("id", vehicle_idx + 1),
                "plate": vehicle.get("plate", ""),
                "driver": vehicle.get("driver", ""),
                "name": vehicle.get("name", f"รถคันที่ {vehicle.get('id', vehicle_idx + 1)}"),
                "capacity": v_capacity,
                "stops": stops,
                "total_weight": round(total_weight, 2),
                "total_distance_km": round(total_distance / 1000, 2),
                "google_maps_link": maps_link,
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
            w = float(order.get("weight", 0))
            if current_weight + w <= v_capacity or not raw:
                raw.append(order)
                current_weight += w
                cursor += 1
            else:
                break

        if raw:
            ordered_stops = _tsp_nearest_neighbor(raw, depot_lat, depot_lng)

            formatted = []
            for stop in ordered_stops:
                formatted.append({
                    "id": stop.get("id"),
                    "customer": stop.get("customer", ""),
                    "address": stop.get("address", ""),
                    "weight": float(stop.get("weight", 0)),
                    "lat": stop.get("lat"),
                    "lng": stop.get("lng"),
                    "raw_lat": stop.get("raw_lat", stop.get("lat")),
                    "raw_lng": stop.get("raw_lng", stop.get("lng")),
                    "verified_lat": stop.get("verified_lat", stop.get("lat")),
                    "verified_lng": stop.get("verified_lng", stop.get("lng")),
                    "confidence_score": stop.get("confidence_score", 30.0),
                    "geocode_provider": stop.get("geocode_provider", "google"),
                    "is_verified": bool(stop.get("is_verified", False)),
                    "order_number": stop.get("order_number"),
                    "zone": stop.get("zone", ""),
                    "products": stop.get("products", []),
                })

            maps_link = generate_google_maps_link(formatted, None)

            routes.append({
                "vehicle_id": vehicle.get("id", v_idx + 1),
                "plate": vehicle.get("plate", ""),
                "driver": vehicle.get("driver", ""),
                "name": vehicle.get("name", f"รถคันที่ {vehicle.get('id', v_idx + 1)}"),
                "capacity": v_capacity,
                "stops": formatted,
                "total_weight": round(current_weight, 2),
                "total_distance_km": 0,
                "google_maps_link": maps_link,
            })

    return routes


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
            dist = _haversine_km(curr_lat, curr_lng, s_lat, s_lng)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx

        nxt = unvisited.pop(best_idx)
        ordered.append(nxt)
        curr_lat = nxt.get("lat", depot_lat)
        curr_lng = nxt.get("lng", depot_lng)

    return ordered


def optimize_routes(
    orders: list[dict],
    distance_matrix: list[list[float]] = None,
    vehicles: list[dict] = None,
    depot: dict = None,
) -> list[dict]:
    """คำนวณเส้นทางจัดส่งด้วย OR-Tools CVRPTW (Capacitated VRP with Time Windows)

    ขั้นตอน:
    1. สร้าง distance matrix (depot = index 0)
    2. เรียก OR-Tools solver พร้อม capacity constraints (ใช้ stop count เป็น demand)
    3. ตรวจสอบ balance — ถ้ารถคันไหนได้น้อยเกินไป ย้ายมา balanced
    4. ถ้าล้มเหลว fallback เป็น Sweep + Nearest Neighbor
    5. คืนค่า list of route dicts
    """
    if not orders:
        return []

    if vehicles is None:
        vehicles = load_vehicles()

    num_vehicles = len(vehicles)
    if num_vehicles == 0:
        logger.warning("ไม่มีรถที่เปิดใช้งานในระบบ")
        return []

    depot_lat = depot.get("lat", 13.781882) if depot else 13.781882
    depot_lng = depot.get("lng", 100.425041) if depot else 100.425041

    # สร้าง distance matrix (depot = index 0, orders = index 1..n)
    if distance_matrix is None or len(distance_matrix) != len(orders) + 1:
        logger.info("สร้าง distance matrix ใหม่ (ไม่ได้รับจาก caller)")
        all_points = [{"lat": depot_lat, "lng": depot_lng}] + orders
        n = len(all_points)
        matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    lat1 = all_points[i].get("lat", depot_lat)
                    lng1 = all_points[i].get("lng", depot_lng)
                    lat2 = all_points[j].get("lat", depot_lat)
                    lng2 = all_points[j].get("lng", depot_lng)
                    matrix[i][j] = _haversine_km(lat1, lng1, lat2, lng2)
        distance_matrix = matrix

    # แปลงเป็น int (เมตร) สำหรับ OR-Tools
    dm_int = _distance_matrix_to_int_km(distance_matrix)

    # ── Demand = จำนวน stop (ไม่ใช่น้ำหนัก) ──
    # เพราะน้ำหนัก orders อาจเบาเกินไป (1 kg/จุด) ทำให้รถคันเดียวจุหมด
    # ใช้ max_stops ต่อรถเป็น capacity ถ้ามี, ไม่งั้นใช้ ceil(total/vehicles) + buffer
    avg_stops = math.ceil(len(orders) / num_vehicles) if num_vehicles > 0 else len(orders)
    vehicle_capacities = []
    for v in vehicles:
        max_stops = v.get("max_stops", 0)
        if max_stops and max_stops > 0:
            vehicle_capacities.append(int(max_stops))
        else:
            # ใช้ 1.5x ของค่าเฉลี่ย เพื่อให้มีพื้นที่เหลือ
            vehicle_capacities.append(int(avg_stops * 1.5) + 1)

    # demand แต่ละจุด = 1 stop
    order_demands = [1] + [1] * len(orders)  # depot = 0

    # แก้ปัญหา VRP
    logger.info(f"กำลังแก้ปัญหา VRP: {len(orders)} orders, {num_vehicles} vehicles, avg_stops={avg_stops} (timeout={SOLVE_TIMEOUT_SECONDS}s)")

    result = _solve_vrp(
        distance_matrix_int=dm_int,
        num_vehicles=num_vehicles,
        vehicle_capacities=vehicle_capacities,
        order_demands=order_demands,
        depot_index=0,
    )

    if result is not None:
        routes = _extract_routes(result, orders, vehicles)
        total_stops = sum(len(r["stops"]) for r in routes)
        logger.info(f"OR-Tools VRP สำเร็จ: {len(routes)} routes, {total_stops} stops")

        # ── Post-processing: Balance routes ──
        routes = _rebalance_routes(routes, orders, vehicles, depot_lat, depot_lng)
        return routes

    # Fallback
    logger.warning("OR-Tools VRP ล้มเหลว — ใช้ Sweep + Nearest Neighbor แทน")
    routes = _fallback_sweep(orders, vehicles, depot_lat, depot_lng)
    total_stops = sum(len(r["stops"]) for r in routes)
    logger.info(f"Fallback: {len(routes)} routes, {total_stops} stops")
    return routes


def _rebalance_routes(
    routes: list[dict],
    orders: list[dict],
    vehicles: list[dict],
    depot_lat: float,
    depot_lng: float,
) -> list[dict]:
    """ตรวจสอบความสมดุลของ routes — ถ้ารถคันไหนได้น้อยกว่า 30% ของค่าเฉลี่ย ย้าย stop มา balanced"""
    if not routes or len(routes) <= 1:
        return routes

    total_stops = sum(len(r["stops"]) for r in routes)
    if total_stops == 0:
        return routes

    avg = total_stops / len(routes)
    min_acceptable = max(1, avg * 0.3)

    # 辆车ที่ไม่มี stop เลย ต้องเพิ่มเข้าไปใน underloaded
    active_route_ids = {r["vehicle_id"] for r in routes}
    for v in vehicles:
        if v.get("active", True) and v.get("id") not in active_route_ids:
            empty_route = {
                "vehicle_id": v.get("id"),
                "plate": v.get("plate", ""),
                "driver": v.get("driver", ""),
                "name": v.get("name", f"รถคันที่ {v.get('id')}"),
                "capacity": float(v.get("capacity", 3750)),
                "stops": [],
                "total_weight": 0,
                "total_distance_km": 0,
                "google_maps_link": "",
            }
            routes.append(empty_route)

    # 重新คำนวณ
    total_stops = sum(len(r["stops"]) for r in routes)
    avg = total_stops / len(routes)
    min_acceptable = max(1, avg * 0.3)

    underloaded = [r for r in routes if len(r["stops"]) < min_acceptable]
    overloaded = [r for r in routes if len(r["stops"]) > avg * 1.2]

    if not underloaded:
        return routes

    logger.info(f"Rebalancing: {len(underloaded)} underloaded vehicles (avg={avg:.1f}, min={min_acceptable:.1f})")

    for under in underloaded:
        if not overloaded:
            overloaded = [r for r in routes if r is not under and len(r["stops"]) > 1]
            if not overloaded:
                break

        # หา stop ที่ใกล้ vehicle under ที่สุด จาก overloaded vehicle
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
                dist = _haversine_km(ref_lat, ref_lng, s_lat, s_lng)
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

    # ลบ routes ที่ไม่มี stop ออก
    routes = [r for r in routes if len(r["stops"]) > 0]

    return routes
