"""Delivery status and route detail operations."""

import json
import logging
import math
import time
from datetime import datetime, timezone
from sqlalchemy import text

from database.connection import SessionLocal, _business_today, _record_db_metric
from database.models import RouteDetail, RoutePlan, Vehicle, StopStatusHistory, ItemDelivery, OrderItem
from config import AUTO_ARRIVAL_MAX_ACCURACY_M, AUTO_ARRIVAL_RADIUS_M
from services.geo_utils import haversine_km

logger = logging.getLogger(__name__)


def update_stop_status(route_id: int, stop_id: int, new_status: str, updated_by: str = "driver", note: str = "", order_id: int = None) -> dict:
    """อัปเดตสถานะของ stop ใน route + บันทึก history"""
    from services.delivery_status import validate_transition

    db = SessionLocal()
    start_time = time.time()
    try:
        route = db.query(RouteDetail).filter(RouteDetail.id == route_id).first()
        if not route:
            return {"success": False, "error": "ไม่พบเส้นทาง"}

        stops = json.loads(route.stops_json) if route.stops_json else []

        target_stop = None
        stop_index = -1
        for i, s in enumerate(stops):
            if s.get("id") == stop_id or s.get("order_number") == str(stop_id):
                target_stop = s
                stop_index = i
                break

        if target_stop is None:
            return {"success": False, "error": "ไม่พบจุดจอดในเส้นทาง"}

        current_status = target_stop.get("delivery_status", "PENDING")

        if not validate_transition(current_status, new_status):
            return {
                "success": False,
                "error": f"ไม่สามารถเปลี่ยนสถานะจาก {current_status} เป็น {new_status} ได้"
            }

        now = datetime.now(timezone.utc).isoformat()
        stops[stop_index]["delivery_status"] = new_status
        stops[stop_index]["status_updated_at"] = now
        stops[stop_index]["status_updated_by"] = updated_by

        if new_status == "ARRIVED":
            stops[stop_index]["arrived_at"] = now
        elif new_status == "DELIVERED":
            stops[stop_index]["delivered_at"] = now
        elif new_status == "FAILED":
            stops[stop_index]["failed_at"] = now
            stops[stop_index]["failure_reason"] = note
        elif new_status == "PARTIAL":
            stops[stop_index]["partial_at"] = now

        route.stops_json = json.dumps(stops, ensure_ascii=False)

        actual_order_id = order_id or target_stop.get("order_id") or target_stop.get("id")
        history = StopStatusHistory(
            stop_id=stop_id,
            route_id=route_id,
            order_id=actual_order_id,
            status=new_status,
            updated_by=updated_by,
            note=note
        )
        db.add(history)
        db.commit()
        _record_db_metric("update", "stop_status", start_time, True)

        logger.info(f"Stop #{stop_id} status: {current_status} → {new_status} (by {updated_by})")
        return {
            "success": True,
            "stop_id": stop_id,
            "previous_status": current_status,
            "new_status": new_status,
            "updated_at": now
        }
    except Exception as e:
        db.rollback()
        _record_db_metric("update", "stop_status", start_time, False)
        logger.error(f"Error updating stop status: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def auto_arrive_stop(
    route_id: int,
    stop_id: int,
    lat: float,
    lng: float,
    accuracy_m: float | None = None,
    updated_by: str = "driver",
    event_id: str | None = None,
    threshold_m: float | None = None,
) -> dict:
    """Mark an in-transit stop ARRIVED when GPS is within the configured radius."""
    threshold = AUTO_ARRIVAL_RADIUS_M if threshold_m is None else threshold_m

    if not all(math.isfinite(value) for value in (lat, lng, threshold)):
        return {"success": False, "error": "พิกัดหรือระยะตรวจสอบไม่ถูกต้อง"}
    if not -90 <= lat <= 90 or not -180 <= lng <= 180 or threshold <= 0:
        return {"success": False, "error": "พิกัดหรือระยะตรวจสอบไม่ถูกต้อง"}
    if accuracy_m is not None:
        if not math.isfinite(accuracy_m) or accuracy_m < 0:
            return {"success": False, "error": "ค่าความแม่นยำ GPS ไม่ถูกต้อง"}
        if accuracy_m > AUTO_ARRIVAL_MAX_ACCURACY_M:
            return {
                "success": True,
                "arrived": False,
                "reason": "gps_accuracy_too_low",
                "threshold_m": threshold,
                "accuracy_m": accuracy_m,
            }

    db = SessionLocal()
    try:
        # Lock the route row on databases that support row-level locking. SQLite
        # ignores FOR UPDATE, but the operation remains safe for local tests.
        route = (
            db.query(RouteDetail)
            .filter(RouteDetail.id == route_id)
            .with_for_update()
            .first()
        )
        if not route:
            return {"success": False, "error": "ไม่พบเส้นทาง"}

        stops = json.loads(route.stops_json) if route.stops_json else []
        target_stop = None
        stop_index = -1
        requested_stop = str(stop_id)
        for index, stop in enumerate(stops):
            if str(stop.get("id")) == requested_stop or str(stop.get("order_number")) == requested_stop:
                target_stop = stop
                stop_index = index
                break

        if target_stop is None:
            return {"success": False, "error": "ไม่พบจุดจอดในเส้นทาง"}

        target_lat = target_stop.get("verified_lat")
        target_lng = target_stop.get("verified_lng")
        if target_lat is None or target_lng is None:
            target_lat = target_stop.get("lat")
            target_lng = target_stop.get("lng")
        if target_lat is None or target_lng is None:
            return {"success": False, "error": "จุดจอดไม่มีพิกัด"}

        distance_m = round(haversine_km(lat, lng, float(target_lat), float(target_lng)) * 1000, 1)
        current_status = str(target_stop.get("delivery_status") or "PENDING").upper()

        if current_status == "ARRIVED":
            return {
                "success": True,
                "arrived": True,
                "idempotent": True,
                "route_id": route_id,
                "stop_id": stop_id,
                "status": current_status,
                "distance_m": distance_m,
                "threshold_m": threshold,
            }

        if current_status != "IN_TRANSIT":
            return {
                "success": True,
                "arrived": False,
                "reason": "status_not_eligible",
                "route_id": route_id,
                "stop_id": stop_id,
                "status": current_status,
                "distance_m": distance_m,
                "threshold_m": threshold,
            }

        if distance_m > threshold:
            return {
                "success": True,
                "arrived": False,
                "reason": "outside_arrival_radius",
                "route_id": route_id,
                "stop_id": stop_id,
                "status": current_status,
                "distance_m": distance_m,
                "threshold_m": threshold,
            }

        now = datetime.now(timezone.utc).isoformat()
        target_stop["delivery_status"] = "ARRIVED"
        target_stop["status_updated_at"] = now
        target_stop["status_updated_by"] = updated_by
        target_stop["arrived_at"] = now
        target_stop["arrival_source"] = "gps"
        target_stop["gps_arrived_lat"] = lat
        target_stop["gps_arrived_lng"] = lng
        target_stop["gps_accuracy_m"] = accuracy_m
        target_stop["arrival_distance_m"] = distance_m
        if event_id:
            target_stop["gps_arrival_event_id"] = event_id

        route.stops_json = json.dumps(stops, ensure_ascii=False)
        db.add(StopStatusHistory(
            stop_id=stop_id,
            route_id=route_id,
            order_id=target_stop.get("order_id") or target_stop.get("id"),
            status="ARRIVED",
            updated_by=updated_by,
            note=f"GPS auto-arrival ({distance_m:.1f}m)",
        ))
        db.commit()

        return {
            "success": True,
            "arrived": True,
            "idempotent": False,
            "route_id": route_id,
            "stop_id": stop_id,
            "status": "ARRIVED",
            "distance_m": distance_m,
            "threshold_m": threshold,
            "updated_at": now,
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error auto-arriving stop: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def get_stop_status_history(route_id: int, stop_id: int = None) -> list[dict]:
    """ดึงประวัติการเปลี่ยนสถานะของ stop"""
    db = SessionLocal()
    try:
        query = db.query(StopStatusHistory).filter(StopStatusHistory.route_id == route_id)
        if stop_id is not None:
            query = query.filter(StopStatusHistory.stop_id == stop_id)

        records = query.order_by(StopStatusHistory.timestamp.desc()).all()
        return [
            {
                "id": r.id,
                "stop_id": r.stop_id,
                "route_id": r.route_id,
                "order_id": r.order_id,
                "status": r.status,
                "timestamp": r.timestamp,
                "updated_by": r.updated_by,
                "note": r.note,
            }
            for r in records
        ]
    finally:
        db.close()


def get_delivery_dashboard() -> dict:
    """ดึงข้อมูล Dashboard สถานะการจัดส่งของวันนี้"""
    db = SessionLocal()
    try:
        today, tz = _business_today()
        plan = db.query(RoutePlan).filter(
            text("DATE(plan_date AT TIME ZONE :tz) = :today")
        ).params(today=today, tz=tz).order_by(RoutePlan.id.desc()).first()

        if not plan:
            return {"has_plan": False, "routes": [], "summary": None}

        details = db.query(RouteDetail).filter(RouteDetail.plan_id == plan.id).order_by(RouteDetail.vehicle_id.asc()).all()

        all_stops = []
        routes_summary = []

        for d in details:
            stops = json.loads(d.stops_json) if d.stops_json else []
            all_stops.extend(stops)

            from services.delivery_status import calculate_delivery_summary
            route_summary = calculate_delivery_summary(stops)
            route_summary["route_id"] = d.id
            route_summary["vehicle_id"] = d.vehicle_id
            route_summary["driver"] = d.driver
            route_summary["plate"] = d.plate
            routes_summary.append(route_summary)

        from services.delivery_status import calculate_delivery_summary
        total_summary = calculate_delivery_summary(all_stops)

        return {
            "has_plan": True,
            "plan_id": plan.id,
            "plan_date": plan.plan_date,
            "routes": routes_summary,
            "summary": total_summary,
        }
    finally:
        db.close()


def update_item_delivery(stop_id: int, order_item_id: int, delivered_qty: float, status: str = "delivered", note: str = "") -> bool:
    """อัปเดตสถานะการจัดส่งระดับ item"""
    db = SessionLocal()
    try:
        existing = db.query(ItemDelivery).filter(
            ItemDelivery.stop_id == stop_id,
            ItemDelivery.order_item_id == order_item_id
        ).first()

        if existing:
            existing.delivered_qty = delivered_qty
            existing.status = status
            existing.note = note
        else:
            order_item = db.query(OrderItem).filter(OrderItem.id == order_item_id).first()
            ordered_qty = order_item.quantity if order_item else 0

            item_delivery = ItemDelivery(
                stop_id=stop_id,
                order_item_id=order_item_id,
                ordered_qty=ordered_qty,
                delivered_qty=delivered_qty,
                status=status,
                note=note
            )
            db.add(item_delivery)

        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating item delivery: {e}")
        return False
    finally:
        db.close()


def reschedule_stop(route_id: int, stop_id: int, reason: str = "", updated_by: str = "dispatcher") -> dict:
    """เลื่อนการจัดส่ง — ย้าย stop กลับเข้า queue"""
    result = update_stop_status(route_id, stop_id, "RESCHEDULED", updated_by, reason)
    if result["success"]:
        logger.info(f"Stop #{stop_id} rescheduled: {reason}")
    return result
