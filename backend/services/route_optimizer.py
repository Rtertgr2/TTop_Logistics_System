import json
import os
import math
import logging
from urllib.parse import quote

from database.db import get_vehicles_from_db

logger = logging.getLogger(__name__)


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


def calculate_angle_and_distance(depot_lat: float, depot_lng: float, lat: float, lng: float) -> tuple[float, float]:
    """คำนวณมุม (Bearing) และระยะห่างจาก Depot สำหรับจัดกลุ่มโซนตามทิศทาง"""
    if not lat or not lng:
        return 0.0, 0.0
    d_lat = lat - depot_lat
    d_lng = lng - depot_lng
    distance = math.sqrt(d_lat**2 + d_lng**2)
    angle = math.atan2(d_lng, d_lat)  # radians (-pi to pi)
    return angle, distance


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


def _optimize_stops_sequence(stops: list[dict], depot_lat: float, depot_lng: float) -> list[dict]:
    """จัดลำดับจุดส่งภายในรถแต่ละคันตามระยะทางใกล้สุด (Nearest Neighbor TSP)"""
    if len(stops) <= 1:
        return stops

    curr_lat, curr_lng = depot_lat, depot_lng
    unvisited = list(stops)
    ordered = []

    while unvisited:
        nearest_idx = 0
        min_dist = float("inf")
        for idx, stop in enumerate(unvisited):
            s_lat = stop.get("lat", depot_lat)
            s_lng = stop.get("lng", depot_lng)
            dist = math.sqrt((curr_lat - s_lat)**2 + (curr_lng - s_lng)**2)
            if dist < min_dist:
                min_dist = dist
                nearest_idx = idx

        nxt = unvisited.pop(nearest_idx)
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
    """คำนวณจัดรถและกระจายออเดอร์ให้รถทุกคันใน Fleet (Balanced Fleet Workload Distribution)
    
    หลักการทำงาน:
    1. ดึงข้อมูลรถที่เปิดใช้งาน (Active Vehicles)
    2. เรียงออเดอร์ตามทิศทางมุมองศาจาก Depot (Geographic Bearing Sector) เพื่อให้จุดที่อยู่โซนใกล้กันถูกกลุ่มเข้าด้วยกัน
    3. แบ่งกลุ่มกระจายจุดส่งให้รถทุกคันเท่าๆ กันตามขีดจำกัดน้ำหนัก (Capacity & Fleet Balancing)
    4. จัดลำดับจุดส่งภายในรถแต่ละคันให้ประหยัดระยะทางที่สุด (TSP Nearest Neighbor)
    """
    if not orders:
        return []

    if vehicles is None:
        vehicles = load_vehicles()

    depot_lat = depot.get("lat", 13.781882) if depot else 13.781882
    depot_lng = depot.get("lng", 100.425041) if depot else 100.425041

    num_vehicles = len(vehicles)
    if num_vehicles == 0:
        logger.warning("ไม่มีรถที่เปิดใช้งานในระบบ")
        return []

    # 1. คำนวณมุมทิศทางจาก Depot ให้แต่ละออเดอร์
    for order in orders:
        lat = order.get("lat", depot_lat)
        lng = order.get("lng", depot_lng)
        angle, dist = calculate_angle_and_distance(depot_lat, depot_lng, lat, lng)
        order["_angle"] = angle
        order["_distance_from_depot"] = dist

    # 2. เรียงออเดอร์ตามทิศทางมุมองศา
    sorted_orders = sorted(orders, key=lambda x: x.get("_angle", 0))
    total_orders = len(sorted_orders)

    # 3. กระจายออเดอร์ให้รถทุกคันใน Fleet อย่างสมดุล (Balanced Allocation)
    target_stops_per_vehicle = math.ceil(total_orders / num_vehicles)
    
    routes = []
    order_cursor = 0

    for v_idx, vehicle in enumerate(vehicles):
        if order_cursor >= total_orders:
            break

        v_capacity = float(vehicle.get("capacity", 3750))
        current_weight = 0.0
        vehicle_stops_raw = []

        # กำหนดโควตาจำนวนจุดส่งสำหรับคันนี้
        # คันสุดท้ายเก็บส่วนที่เหลือทั้งหมด
        max_stops_for_this_car = target_stops_per_vehicle if v_idx < num_vehicles - 1 else (total_orders - order_cursor)

        while order_cursor < total_orders and len(vehicle_stops_raw) < max_stops_for_this_car:
            order = sorted_orders[order_cursor]
            o_weight = float(order.get("weight", 0))

            # หากน้ำหนักบรรทุกยังไม่เกินความจุรถ
            if current_weight + o_weight <= v_capacity or len(vehicle_stops_raw) == 0:
                vehicle_stops_raw.append(order)
                current_weight += o_weight
                order_cursor += 1
            else:
                # ถ้าน้ำหนักเกิน ให้ตัดไปขึ้นรถคันถัดไป
                break

        if vehicle_stops_raw:
            # 4. เรียงลำดับจุดส่งภายในรถแต่ละคันให้ประหยัดระยะทางที่สุด
            ordered_stops = _optimize_stops_sequence(vehicle_stops_raw, depot_lat, depot_lng)
            
            # แปลงเป็น dict สำหรับ response
            formatted_stops = []
            for stop in ordered_stops:
                formatted_stops.append({
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
                    "products": stop.get("products", [])
                })

            maps_link = generate_google_maps_link(formatted_stops, depot)

            routes.append({
                "vehicle_id": vehicle.get("id", v_idx + 1),
                "plate": vehicle.get("plate", ""),
                "driver": vehicle.get("driver", ""),
                "name": vehicle.get("name", f"รถคันที่ {vehicle.get('id', v_idx + 1)}"),
                "capacity": v_capacity,
                "stops": formatted_stops,
                "total_weight": round(current_weight, 2),
                "google_maps_link": maps_link,
            })

    logger.info(f"จัดกระจายรถสำเร็จ: กระจายงานลงรถ {len(routes)}/{num_vehicles} คัน, รวม {sum(len(r['stops']) for r in routes)} จุดส่ง")
    return routes
