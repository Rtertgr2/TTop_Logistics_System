"""Customer location memory operations."""

import logging
from datetime import UTC, datetime

from database.connection import SessionLocal
from database.models import CustomerLocation

logger = logging.getLogger(__name__)


def get_saved_customer_location(customer: str, address: str) -> dict | None:
    """ดึงพิกัดที่เคยยืนยันแล้วจากตาราง customer_locations"""
    if not customer and not address:
        return None

    db = SessionLocal()
    try:
        clean_key = (
            (customer.strip() if customer else "")
            + "_"
            + (address.strip() if address else "")
        )
        clean_key = clean_key.lower().replace(" ", "")

        location = (
            db.query(CustomerLocation)
            .filter(
                (CustomerLocation.customer_key == clean_key)
                | (CustomerLocation.address_key == clean_key)
            )
            .first()
        )

        if location:
            return {
                "lat": location.lat,
                "lng": location.lng,
                "formatted_address": location.formatted_address,
                "confidence_score": location.confidence_score or 100.0,
                "geocode_provider": "database_memory",
                "is_verified": True,
            }
        return None
    finally:
        db.close()


def save_customer_location(
    customer: str,
    address: str,
    lat: float,
    lng: float,
    formatted_address: str = "",
    confidence_score: float = 100.0,
    db=None,
) -> bool:
    """บันทึก/อัปเดตพิกัดลูกค้าลงตาราง customer_locations เพื่อใช้จำถาวร
    ถ้าส่ง db มา จะใช้ session เดียวกันกับ caller (ไม่ commit/close เอง)"""
    if lat is None or lng is None:
        return False

    clean_key = (
        (customer.strip() if customer else "")
        + "_"
        + (address.strip() if address else "")
    )
    clean_key = clean_key.lower().replace(" ", "")
    if len(clean_key) < 2:
        return False

    _owns_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        existing = (
            db.query(CustomerLocation)
            .filter(CustomerLocation.customer_key == clean_key)
            .first()
        )

        if existing:
            existing.lat = lat
            existing.lng = lng
            existing.formatted_address = formatted_address or address
            existing.confidence_score = confidence_score
            existing.updated_at = datetime.now(UTC)
        else:
            location = CustomerLocation(
                customer_key=clean_key,
                address_key=clean_key,
                lat=lat,
                lng=lng,
                formatted_address=formatted_address or address,
                confidence_score=confidence_score,
                updated_at=datetime.now(UTC),
            )
            db.add(location)

        if _owns_session:
            db.commit()
        logger.info(f"Saved location memory for key '{clean_key}' => ({lat}, {lng})")
        return True
    except Exception as e:
        if _owns_session:
            db.rollback()
        logger.error(f"Error saving customer location: {e}")
        return False
    finally:
        if _owns_session:
            db.close()


def get_all_customer_locations(limit: int = 200) -> list[dict]:
    """ดึงข้อมูลพิกัดความจำถาวรของลูกค้าทั้งหมด"""
    db = SessionLocal()
    try:
        locations = (
            db.query(CustomerLocation)
            .order_by(CustomerLocation.updated_at.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": loc.id,
                "customer_key": loc.customer_key,
                "lat": loc.lat,
                "lng": loc.lng,
                "formatted_address": loc.formatted_address,
                "confidence_score": loc.confidence_score,
                "updated_at": loc.updated_at,
            }
            for loc in locations
        ]
    finally:
        db.close()


def delete_customer_location(loc_id: int) -> bool:
    """ลบพิกัดความจำถาวรของลูกค้าตาม ID"""
    db = SessionLocal()
    try:
        location = (
            db.query(CustomerLocation).filter(CustomerLocation.id == loc_id).first()
        )
        if location:
            db.delete(location)
            db.commit()
            return True
        return False
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting customer location: {e}")
        return False
    finally:
        db.close()
