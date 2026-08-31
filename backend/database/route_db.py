"""Route plan CRUD operations."""

import json
import logging
import time
from datetime import UTC, datetime

from sqlalchemy import text

from database.connection import SessionLocal, _business_today, _record_db_metric
from database.models import (
    CustomerLocation,
    ItemDelivery,
    Order,
    OrderItem,
    RouteDetail,
    RoutePlan,
    RouteTransfer,
    StopStatusHistory,
    Vehicle,
)

logger = logging.getLogger(__name__)


def save_route_plan(routes: list[dict], depot: dict | None = None) -> int:
    """บันทึกผลการจัดคิวรถ (Route Plan) ลง Database"""
    db = SessionLocal()
    start_time = time.time()
    try:
        plan_date = datetime.now(UTC)
        total_orders = sum(len(r.get("stops", [])) for r in routes)
        total_vehicles = len(routes)
        depot_addr = depot.get("address", "") if depot else ""

        plan = RoutePlan(
            plan_date=plan_date,
            total_orders=total_orders,
            total_vehicles=total_vehicles,
            depot_address=depot_addr,
        )
        db.add(plan)
        db.flush()

        plan_id = plan.id

        for route in routes:
            stops_json = json.dumps(route.get("stops", []), ensure_ascii=False)
            detail = RouteDetail(
                plan_id=plan_id,
                vehicle_id=route.get("vehicle_id"),
                plate=route.get("plate"),
                driver=route.get("driver"),
                total_weight=route.get("total_weight"),
                google_maps_link=route.get("google_maps_link"),
                stops_json=stops_json,
            )
            db.add(detail)

        db.commit()
        _record_db_metric("save", "route_plans", start_time, True)
        logger.info(
            f"Saved Route Plan #{plan_id} with {len(routes)} vehicles to Database"
        )
        return plan_id
    except Exception as e:
        db.rollback()
        _record_db_metric("save", "route_plans", start_time, False)
        logger.error(f"Error saving route plan: {e}")
        raise
    finally:
        db.close()


def get_today_active_routes() -> list[dict]:
    """ดึงแผนการเดินรถล่าสุดของวันนี้ (ตัดรอบเที่ยงคืนตาม BUSINESS_TIMEZONE)"""
    db = SessionLocal()
    try:
        today, tz = _business_today()
        plan = (
            db.query(RoutePlan)
            .filter(text("DATE(plan_date AT TIME ZONE :tz) = :today"))
            .params(today=today, tz=tz)
            .order_by(RoutePlan.id.desc())
            .first()
        )

        if not plan:
            return []

        details = (
            db.query(RouteDetail)
            .filter(RouteDetail.plan_id == plan.id)
            .order_by(RouteDetail.vehicle_id.asc())
            .all()
        )
        capacity_map = {v.id: v.capacity for v in db.query(Vehicle).all()}
        routes = []
        for d in details:
            rd = {
                "id": d.id,
                "plan_id": d.plan_id,
                "vehicle_id": d.vehicle_id,
                "plate": d.plate,
                "driver": d.driver,
                "capacity": capacity_map.get(d.vehicle_id, 3750),
                "total_weight": d.total_weight,
                "google_maps_link": d.google_maps_link,
                "stops": json.loads(d.stops_json) if d.stops_json else [],
            }
            routes.append(rd)
        return routes
    finally:
        db.close()


def get_route_history(limit: int = 20) -> list[dict]:
    """ดึงประวัติการจัดคิวรถย้อนหลัง"""
    db = SessionLocal()
    try:
        plans = db.query(RoutePlan).order_by(RoutePlan.id.desc()).limit(limit).all()
        capacity_map = {v.id: v.capacity for v in db.query(Vehicle).all()}
        result = []
        for plan in plans:
            p = {
                "id": plan.id,
                "plan_date": plan.plan_date,
                "total_orders": plan.total_orders,
                "total_vehicles": plan.total_vehicles,
                "depot_address": plan.depot_address,
                "created_at": plan.created_at,
            }

            details = (
                db.query(RouteDetail)
                .filter(RouteDetail.plan_id == plan.id)
                .order_by(RouteDetail.vehicle_id.asc())
                .all()
            )
            routes = []
            for d in details:
                rd = {
                    "id": d.id,
                    "plan_id": d.plan_id,
                    "vehicle_id": d.vehicle_id,
                    "plate": d.plate,
                    "driver": d.driver,
                    "capacity": capacity_map.get(d.vehicle_id, 3750),
                    "total_weight": d.total_weight,
                    "google_maps_link": d.google_maps_link,
                    "stops": json.loads(d.stops_json) if d.stops_json else [],
                }
                routes.append(rd)
            p["routes"] = routes
            result.append(p)
        return result
    finally:
        db.close()


def get_route_driver_name(route_id: int) -> str | None:
    """ดึงชื่อคนขับที่เป็นเจ้าของ RouteDetail (สำหรับตรวจสอบสิทธิ์)"""
    db = SessionLocal()
    try:
        detail = db.query(RouteDetail).filter(RouteDetail.id == route_id).first()
        return detail.driver if detail else None
    finally:
        db.close()


def get_driver_route(driver_name: str) -> dict | None:
    """ดึงเส้นทางของคนขับวันนี้"""
    from services.delivery_status import calculate_delivery_summary

    db = SessionLocal()
    try:
        today, tz = _business_today()
        plan = (
            db.query(RoutePlan)
            .filter(text("DATE(plan_date AT TIME ZONE :tz) = :today"))
            .params(today=today, tz=tz)
            .order_by(RoutePlan.id.desc())
            .first()
        )

        if not plan:
            return None

        details = (
            db.query(RouteDetail)
            .filter(RouteDetail.plan_id == plan.id, RouteDetail.driver == driver_name)
            .all()
        )

        if not details:
            return None

        merged_stops = []
        primary = details[0]
        total_weight = 0.0
        for d in details:
            stops = json.loads(d.stops_json) if d.stops_json else []
            for stop in stops:
                stop.setdefault("route_detail_id", d.id)
            merged_stops.extend(stops)
            total_weight += float(d.total_weight or 0)

        summary = calculate_delivery_summary(merged_stops)

        return {
            "route_id": primary.id,
            "plan_id": primary.plan_id,
            "vehicle_id": primary.vehicle_id,
            "plate": primary.plate,
            "driver": primary.driver,
            "total_weight": round(total_weight, 1),
            "google_maps_link": primary.google_maps_link,
            "stops": merged_stops,
            "summary": summary,
        }
    finally:
        db.close()


def clear_all_data():
    """ลบข้อมูลออเดอร์ + ประวัติแผนจัดส่งทั้งหมด (รถ + คนขับ + LINE id ไม่ถูกลบ)"""
    db = SessionLocal()
    try:
        db.query(ItemDelivery).delete()
        db.query(StopStatusHistory).delete()
        db.query(RouteTransfer).delete()
        db.query(OrderItem).delete()
        db.query(Order).delete()
        db.query(RouteDetail).delete()
        db.query(RoutePlan).delete()
        db.query(CustomerLocation).delete()
        db.commit()

        try:
            db.execute(text("ALTER SEQUENCE orders_id_seq RESTART WITH 1"))
            db.execute(text("ALTER SEQUENCE order_items_id_seq RESTART WITH 1"))
            db.execute(text("ALTER SEQUENCE route_plans_id_seq RESTART WITH 1"))
            db.execute(text("ALTER SEQUENCE route_details_id_seq RESTART WITH 1"))
            db.execute(text("ALTER SEQUENCE customer_locations_id_seq RESTART WITH 1"))
            db.commit()
        except Exception as e:
            logger.warning(f"Could not reset sequences: {e}")

        logger.info("ล้างข้อมูลออเดอร์ + ประวัติแผนเรียบร้อยแล้ว (ข้อมูลรถคงเดิม)")
    except Exception as e:
        db.rollback()
        logger.error(f"Error clearing data: {e}")
        raise
    finally:
        db.close()
