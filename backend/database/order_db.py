"""Order CRUD operations."""

import json
import logging
import time
from datetime import UTC, datetime

from sqlalchemy import text

from database.connection import SessionLocal, _business_today, _record_db_metric
from database.models import Order, OrderItem, RouteDetail, RoutePlan

logger = logging.getLogger(__name__)


def _order_to_dict(order: Order) -> dict:
    """แปลง Order object เป็น dict"""
    r = {
        "id": order.id,
        "order_number": order.order_number,
        "customer": order.customer,
        "address": order.address,
        "weight": order.weight,
        "source_file": order.source_file,
        "lat": order.lat,
        "lng": order.lng,
        "raw_lat": order.raw_lat,
        "raw_lng": order.raw_lng,
        "verified_lat": order.verified_lat,
        "verified_lng": order.verified_lng,
        "confidence_score": order.confidence_score,
        "geocode_provider": order.geocode_provider,
        "is_verified": order.is_verified,
        "verified_by": order.verified_by,
        "verified_at": order.verified_at,
        "zone": order.zone,
        "products_json": order.products_json,
        "created_at": order.created_at,
        "delivery_date": order.delivery_date,
        "booking_status": order.booking_status,
    }
    if r.get("products_json"):
        try:
            r["products"] = json.loads(r["products_json"])
        except Exception:
            r["products"] = []
    return r


def save_orders(orders: list[dict]) -> list[int]:
    """บันทึกรายการออเดอร์ลง Database"""
    if not orders:
        return []

    db = SessionLocal()
    saved_ids = []
    start_time = time.time()

    try:
        for order in orders:
            products_json = json.dumps(order.get("products", []), ensure_ascii=False)
            lat = order.get("lat")
            lng = order.get("lng")

            db_order = Order(
                order_number=order.get("order_number"),
                customer=order.get("customer", "ไม่ระบุ"),
                address=order.get("address", "ไม่ระบุ"),
                weight=order.get("weight", 0),
                source_file=order.get("source_file"),
                lat=lat,
                lng=lng,
                raw_lat=order.get("raw_lat", lat),
                raw_lng=order.get("raw_lng", lng),
                verified_lat=order.get("verified_lat", lat),
                verified_lng=order.get("verified_lng", lng),
                confidence_score=order.get("confidence_score", 95.0),
                geocode_provider=order.get("geocode_provider", "google"),
                is_verified=1 if order.get("is_verified") else 0,
                verified_by=order.get("verified_by"),
                verified_at=order.get("verified_at"),
                zone=order.get("zone"),
                products_json=products_json,
                created_at=datetime.now(UTC),
            )
            db.add(db_order)
            db.flush()

            new_id = db_order.id
            saved_ids.append(new_id)
            # เขียน id กลับเข้า order dict (เหมือนเดิม) เพื่อให้ frontend/driver update-status ใช้ stop id ได้
            order["id"] = new_id

            products = order.get("products", [])
            if products:
                for p in products:
                    db_item = OrderItem(
                        order_id=new_id,
                        product_code=p.get("code", ""),
                        product_name=p.get("name", ""),
                        quantity=p.get("quantity", 0),
                        unit=p.get("unit", "ชิ้น"),
                        price=p.get("price", 0),
                        total=p.get("total", 0),
                        item_weight=p.get("item_weight", 0),
                    )
                    db.add(db_item)

        db.commit()
        _record_db_metric("save", "orders", start_time, True)
        logger.info(f"Saved {len(saved_ids)} orders to Database")
        return saved_ids
    except Exception as e:
        db.rollback()
        _record_db_metric("save", "orders", start_time, False)
        logger.error(f"Error saving orders: {e}")
        raise
    finally:
        db.close()


def get_all_orders(limit: int = 100) -> list[dict]:
    """ดึงรายการออเดอร์ล่าสุดจาก Database"""
    db = SessionLocal()
    try:
        orders = db.query(Order).order_by(Order.id.desc()).limit(limit).all()
        return [_order_to_dict(order) for order in orders]
    finally:
        db.close()


def get_today_orders() -> list[dict]:
    """ดึงรายการออเดอร์เฉพาะวันปัจจุบัน (ตัดรอบเที่ยงคืนตาม BUSINESS_TIMEZONE)"""
    db = SessionLocal()
    try:
        today, tz = _business_today()
        orders = (
            db.query(Order)
            .filter(text("DATE(created_at AT TIME ZONE :tz) = :today"))
            .params(today=today, tz=tz)
            .order_by(Order.id.desc())
            .all()
        )
        return [_order_to_dict(order) for order in orders]
    finally:
        db.close()


def update_order_location(
    order_id: int, lat: float, lng: float, verified_by: str = "user"
) -> bool:
    """อัปเดตและยืนยันพิกัดตำแหน่งจริงของออเดอร์ พร้อมเซฟเข้าความจำความแม่นยำถาวร"""
    from database.location_db import save_customer_location

    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return False

        order.lat = lat
        order.lng = lng
        order.verified_lat = lat
        order.verified_lng = lng
        order.confidence_score = 100.0
        order.is_verified = 1
        order.verified_by = verified_by
        order.verified_at = datetime.now(UTC)

        save_customer_location(
            order.customer,
            order.address,
            lat,
            lng,
            f"Verified Location ({lat}, {lng})",
            100.0,
            db=db,
        )

        try:
            today, tz = _business_today()
            plan = (
                db.query(RoutePlan)
                .filter(text("DATE(plan_date AT TIME ZONE :tz) = :today"))
                .params(today=today, tz=tz)
                .order_by(RoutePlan.id.desc())
                .first()
            )
            if plan:
                details = (
                    db.query(RouteDetail).filter(RouteDetail.plan_id == plan.id).all()
                )
                for d in details:
                    stops = json.loads(d.stops_json) if d.stops_json else []
                    changed = False
                    for s in stops:
                        if s.get("id") == order_id or s.get("order_id") == order_id:
                            s["lat"] = lat
                            s["lng"] = lng
                            s["verified_lat"] = lat
                            s["verified_lng"] = lng
                            s["is_verified"] = True
                            changed = True
                    if changed:
                        d.stops_json = json.dumps(stops, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Could not sync stops_json for order {order_id}: {e}")

        db.commit()
        logger.info(
            f"Updated location for Order #{order_id} => ({lat}, {lng}) by {verified_by}"
        )
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating order location: {e}")
        return False
    finally:
        db.close()
