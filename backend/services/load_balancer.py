"""
Load Balancing Service
Auto-detect vehicle overflow/underflow and suggest transfers.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Thresholds ──────────────────────────────────────────────────

OVERFLOW_THRESHOLD = 0.90      # >= 90% = "รถเต็ม"
UNDERFLOW_THRESHOLD = 0.40     # <= 40% = "รถว่างเกิน"
TARGET_MIN = 0.60              # เป้าหมาย transfer: >= 60%
TARGET_MAX = 0.85              # เป้าหมาย transfer: <= 85%
SOURCE_MIN_AFTER = 0.30        # ย้ายออกแล้ว source ต้อง >= 30%
MAX_DETOUR_KM = 5.0            # สูงสุดระยะเบี่ยงเบน
MAX_DETOUR_MINUTES = 15        # สูงสุดเวลาเบี่ยงเบน


# ─── Utility ─────────────────────────────────────────────────────

from services.geo_utils import haversine_km


def _route_centroid(stops):
    """คำนวณจุดศูนย์ถ่วงของ route"""
    valid = [(s["lat"], s["lng"]) for s in stops if s.get("lat") and s.get("lng")]
    if not valid:
        return None, None
    return sum(la for la, _ in valid) / len(valid), sum(lo for _, lo in valid) / len(valid)


def _calculate_route_weight(stops):
    """คำนวณน้ำหนักรวมของ route"""
    return sum(s.get("weight", 0) for s in stops)


# ─── Utilization Calculation ─────────────────────────────────────

def calculate_utilization(route: dict, vehicle_capacity: float = None) -> dict:
    """คำนวณ utilization ของรถแต่ละคัน"""
    capacity = vehicle_capacity or route.get("capacity", 3750)
    stops = route.get("stops") or []
    weight = _calculate_route_weight(stops)
    num_stops = len(stops)

    weight_pct = weight / capacity if capacity > 0 else 0

    # Determine status
    if weight_pct >= OVERFLOW_THRESHOLD:
        status = "overflow"
    elif weight_pct <= UNDERFLOW_THRESHOLD:
        status = "underflow"
    elif weight_pct >= 0.70:
        status = "high"
    else:
        status = "normal"

    return {
        "route_id": route.get("id"),
        "vehicle_id": route.get("vehicle_id"),
        "driver": route.get("driver"),
        "plate": route.get("plate"),
        "capacity": capacity,
        "current_weight": round(weight, 1),
        "num_stops": num_stops,
        "weight_pct": round(weight_pct * 100, 1),
        "status": status,
    }


# ─── Auto-Detect ─────────────────────────────────────────────────

def detect_imbalances(routes: list[dict]) -> dict:
    """ตรวจจับรถที่เต็มหรือว่างเกิน"""
    vehicles = []
    for route in routes:
        cap = route.get("capacity", 3750)
        util = calculate_utilization(route, cap)
        vehicles.append(util)

    overflow = [v for v in vehicles if v["status"] == "overflow"]
    underflow = [v for v in vehicles if v["status"] == "underflow"]
    high = [v for v in vehicles if v["status"] == "high"]
    normal = [v for v in vehicles if v["status"] == "normal"]

    return {
        "vehicles": vehicles,
        "overflow": overflow,
        "underflow": underflow,
        "high": high,
        "normal": normal,
        "needs_transfer": len(overflow) > 0 or len(underflow) > 0,
    }


# ─── Transfer Scoring ────────────────────────────────────────────

def _score_transfer(source_stops, candidate_stop, target_centroid, target_capacity, target_weight, avg_speed_kmh=30):
    """คำนวณ Transfer Score (ยิ่งต่ำ = ยิ่งคุ้มค่า)"""
    score = 0.0

    # 1. Detour distance (km) — ระยะทางเบี่ยงเบน
    stop_lat = candidate_stop.get("lat", 0)
    stop_lng = candidate_stop.get("lng", 0)
    detour_km = haversine_km(
        target_centroid[0], target_centroid[1],
        stop_lat, stop_lng
    )
    score += detour_km * 10  # 10 points per km

    # 2. Time penalty (minutes)
    time_penalty = (detour_km / max(avg_speed_kmh, 1)) * 60 + 5  # 5 min per stop
    score += time_penalty * 2  # 2 points per minute

    # 3. Capacity fit — ย้ายมาแล้ว target อยู่ที่ %
    new_target_weight = target_weight + candidate_stop.get("weight", 0)
    new_target_pct = new_target_weight / target_capacity if target_capacity > 0 else 0

    # ถ้าเกิน 85% = ไม่ควรย้าย
    if new_target_pct > TARGET_MAX:
        return None  # Block transfer

    # ถ้าอยู่ในช่วง 60-85% = ดีมาก (bonus)
    if TARGET_MIN <= new_target_pct <= TARGET_MAX:
        score -= 20  # bonus

    # 4. Time window risk
    tw = candidate_stop.get("time_window_end")
    if tw:
        # ถ้ามี time window แคบ = เสี่ยง
        score += 15

    return round(score, 1)


def find_transfer_suggestions(routes: list[dict], avg_speed_kmh: int = 30) -> list[dict]:
    """หาคำแนะนำการย้าย stop ระหว่างรถ"""
    imbalances = detect_imbalances(routes)
    suggestions = []

    # Build route lookup
    route_map = {}
    for route in routes:
        route_map[route.get("id")] = route

    # For each overflow vehicle, find best underflow targets
    for overflow_info in imbalances["overflow"]:
        overflow_route = route_map.get(overflow_info["route_id"])
        if not overflow_route:
            continue

        overflow_stops = overflow_route.get("stops") or []
        overflow_weight = _calculate_route_weight(overflow_stops)
        overflow_capacity = overflow_info["capacity"]

        # Sort stops by transferability (prefer non-urgent, heavy stops)
        transferable = sorted(
            overflow_stops,
            key=lambda s: (
                -s.get("weight", 0),  # heavier first
                1 if s.get("time_window_end") else 0,  # no time window first
            )
        )

        for candidate_stop in transferable[:5]:  # Top 5 candidates
            # Find best underflow target
            target_scores = []
            for underflow_info in imbalances["underflow"] + imbalances["high"]:
                if underflow_info["route_id"] == overflow_info["route_id"]:
                    continue

                target_route = route_map.get(underflow_info["route_id"])
                if not target_route:
                    continue

                target_stops = target_route.get("stops") or []
                target_centroid = _route_centroid(target_stops)
                if target_centroid[0] is None:
                    continue

                target_weight = _calculate_route_weight(target_stops)
                target_capacity = underflow_info["capacity"]

                score = _score_transfer(
                    overflow_stops, candidate_stop,
                    target_centroid, target_capacity, target_weight,
                    avg_speed_kmh
                )

                if score is not None:
                    target_scores.append({
                        "target_route_id": underflow_info["route_id"],
                        "target_vehicle_id": underflow_info["vehicle_id"],
                        "target_driver": underflow_info["driver"],
                        "target_plate": underflow_info["plate"],
                        "target_weight": round(target_weight, 1),
                        "target_capacity": target_capacity,
                        "target_weight_pct": underflow_info["weight_pct"],
                        "new_target_weight": round(target_weight + candidate_stop.get("weight", 0), 1),
                        "new_target_pct": round((target_weight + candidate_stop.get("weight", 0)) / target_capacity * 100, 1) if target_capacity > 0 else 0,
                        "score": score,
                    })

            # Sort by score (lower = better)
            target_scores.sort(key=lambda x: x["score"])

            if target_scores:
                best = target_scores[0]
                stop_weight = candidate_stop.get("weight", 0)
                new_source_weight = overflow_weight - stop_weight
                new_source_pct = round(new_source_weight / overflow_capacity * 100, 1) if overflow_capacity > 0 else 0

                # Block if source goes below 30%
                if new_source_pct < SOURCE_MIN_AFTER * 100:
                    continue

                suggestions.append({
                    "source_route_id": overflow_info["route_id"],
                    "source_vehicle_id": overflow_info["vehicle_id"],
                    "source_driver": overflow_info["driver"],
                    "source_plate": overflow_info["plate"],
                    "source_weight_before": overflow_info["current_weight"],
                    "source_weight_after": round(new_source_weight, 1),
                    "source_pct_before": overflow_info["weight_pct"],
                    "source_pct_after": new_source_pct,
                    "stop": {
                        "id": candidate_stop.get("id") or candidate_stop.get("order_number"),
                        "customer": candidate_stop.get("customer"),
                        "address": candidate_stop.get("address"),
                        "weight": stop_weight,
                        "lat": candidate_stop.get("lat"),
                        "lng": candidate_stop.get("lng"),
                    },
                    "target": best,
                    "transfer_score": best["score"],
                    "rank": len(suggestions) + 1,
                })

    # Sort by score (best first)
    suggestions.sort(key=lambda x: x["transfer_score"])
    return suggestions[:10]  # Top 10 suggestions


# ─── Execute Transfer ────────────────────────────────────────────

def execute_transfer(
    source_route_id: int,
    target_route_id: int,
    stop_id,
    approved_by: str = "dispatcher"
) -> dict:
    """Execute transfer — ย้าย stop จาก source ไป target"""
    from database.db import SessionLocal
    from database.models import RouteDetail, RouteTransfer
    import json as json_mod

    db = SessionLocal()
    try:
        if source_route_id == target_route_id:
            return {"success": False, "error": "เส้นทางต้นทางและปลายทางต้องไม่เป็นเส้นทางเดียวกัน"}

        # Load source route
        source_route = db.query(RouteDetail).filter(RouteDetail.id == source_route_id).first()
        if not source_route:
            return {"success": False, "error": "ไม่พบเส้นทางต้นทาง"}

        target_route = db.query(RouteDetail).filter(RouteDetail.id == target_route_id).first()
        if not target_route:
            return {"success": False, "error": "ไม่พบเส้นทางปลายทาง"}

        source_stops = json_mod.loads(source_route.stops_json) if source_route.stops_json else []
        target_stops = json_mod.loads(target_route.stops_json) if target_route.stops_json else []

        # Find the stop to move
        stop_to_move = None
        stop_index = -1
        for i, s in enumerate(source_stops):
            if str(s.get("id")) == str(stop_id) or s.get("order_number") == str(stop_id):
                stop_to_move = s
                stop_index = i
                break

        if stop_to_move is None:
            return {"success": False, "error": "ไม่พบจุดจอดในเส้นทางต้นทาง"}

        # Move stop
        source_stops.pop(stop_index)
        stop_to_move["transferred_from"] = source_route_id
        stop_to_move["transferred_at"] = datetime.now(timezone.utc).isoformat()
        target_stops.append(stop_to_move)

        # Re-sequence both source and target stops
        for i, s in enumerate(source_stops):
            s["sequence"] = i + 1
        for i, s in enumerate(target_stops):
            s["sequence"] = i + 1

        # Update weights
        source_weight = _calculate_route_weight(source_stops)
        target_weight = _calculate_route_weight(target_stops)

        # Capacity checks (ใช้ความจุรถจริงจากตาราง Vehicle)
        try:
            from database.models import Vehicle as VehicleModel
            target_veh = db.query(VehicleModel).filter(VehicleModel.id == target_route.vehicle_id).first()
            source_veh = db.query(VehicleModel).filter(VehicleModel.id == source_route.vehicle_id).first()
            target_capacity = target_veh.capacity if target_veh else 3750
            source_capacity = source_veh.capacity if source_veh else 3750
        except Exception:
            target_capacity, source_capacity = 3750, 3750

        TARGET_MAX = 0.95
        SOURCE_MIN_AFTER = 0.30

        if target_weight > target_capacity * TARGET_MAX:
            return {
                "success": False,
                "error": f"ไม่สามารถโอนได้: น้ำหนักปลายทาง {target_weight:.0f}kg เกิน {int(TARGET_MAX*100)}% ของความจุรถ ({target_capacity:.0f}kg)"
            }

        if source_capacity > 0 and (source_weight / source_capacity) < SOURCE_MIN_AFTER:
            return {
                "success": False,
                "error": f"ไม่สามารถโอนได้: เส้นทางต้นทางจะเหลือเพียง {source_weight:.0f}kg (<{int(SOURCE_MIN_AFTER*100)}% ของความจุรถ {source_capacity:.0f}kg)"
            }

        source_route.stops_json = json_mod.dumps(source_stops, ensure_ascii=False)
        source_route.total_weight = round(source_weight, 1)
        target_route.stops_json = json_mod.dumps(target_stops, ensure_ascii=False)
        target_route.total_weight = round(target_weight, 1)

        # Log transfer
        transfer_log = RouteTransfer(
            stop_id=stop_id,
            order_id=stop_to_move.get("order_id") or stop_to_move.get("id"),
            from_route_id=source_route_id,
            to_route_id=target_route_id,
            from_vehicle_id=source_route.vehicle_id,
            to_vehicle_id=target_route.vehicle_id,
            transfer_type="manual",
            reason=f"Load balancing: {stop_to_move.get('customer', '')}",
            approved_by=approved_by,
        )
        db.add(transfer_log)
        db.commit()

        logger.info(f"Transfer executed: stop {stop_id} from route {source_route_id} → {target_route_id}")
        return {
            "success": True,
            "stop_id": stop_id,
            "source_route_id": source_route_id,
            "target_route_id": target_route_id,
            "source_weight_after": round(source_weight, 1),
            "target_weight_after": round(target_weight, 1),
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error executing transfer: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# ─── Re-calculate Route After Transfer ───────────────────────────

def recalculate_route_after_transfer(route_id: int, depot_lat: float = 13.781882, depot_lng: float = 100.425041) -> dict:
    """คำนวณเส้นทางใหม่หลังย้าย stop"""
    from database.db import SessionLocal
    from database.models import RouteDetail
    from services.route_optimizer import _solve_vrp
    from services.distance_matrix_real import _haversine_distance_matrix

    db = SessionLocal()
    try:
        route = db.query(RouteDetail).filter(RouteDetail.id == route_id).first()
        if not route:
            return {"success": False, "error": "ไม่พบเส้นทาง"}

        stops = json.loads(route.stops_json) if route.stops_json else []
        if len(stops) < 2:
            return {"success": True, "message": "ไม่ต้องคำนวณใหม่ (น้อยกว่า 2 จุด)"}

        # Build points for reordering (เฉพาะจุดที่มีพิกัด) — เก็บ index เดิมไว้ด้วย
        coord_stops = [s for s in stops if s.get("lat") and s.get("lng")]
        if len(coord_stops) < 2:
            return {"success": True, "message": "ไม่มีพิกัดพอคำนวณ"}

        points = [{"lat": depot_lat, "lng": depot_lng}] + [{"lat": s["lat"], "lng": s["lng"]} for s in coord_stops]

        # Use simple nearest-neighbor for reordering (fast)
        dm = _haversine_distance_matrix(points)
        ordered = [0]
        remaining = set(range(1, len(points)))
        while remaining:
            last = ordered[-1]
            nearest = min(remaining, key=lambda x: dm[last][x])
            ordered.append(nearest)
            remaining.remove(nearest)

        # เรียง coord stops ตามลำดับที่ได้
        solved_coord = [coord_stops[i - 1] for i in ordered[1:]]

        # ประกอบ reordered คืน: เก็บจุดที่ไม่มีพิกัดไว้ตำแหน่งเดิม (ไม่ตกหล่น)
        reordered = []
        ci = 0
        for s in stops:
            if s.get("lat") and s.get("lng"):
                reordered.append(solved_coord[ci])
                ci += 1
            else:
                reordered.append(s)

        for i, s in enumerate(reordered):
            s["sequence"] = i + 1

        route.stops_json = json.dumps(reordered, ensure_ascii=False)
        route.total_weight = round(_calculate_route_weight(reordered), 1)
        db.commit()

        return {"success": True, "route_id": route_id, "new_sequence": len(reordered)}
    except Exception as e:
        db.rollback()
        logger.error(f"Error recalculating route: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        db.close()
