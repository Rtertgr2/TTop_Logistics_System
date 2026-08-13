"""Vehicle CRUD operations."""

import logging
import time
from sqlalchemy.exc import OperationalError

from database.connection import SessionLocal, _record_db_metric
from database.models import Vehicle

logger = logging.getLogger(__name__)


def save_vehicles_to_db(vehicles_list: list[dict]):
    """บันทึก/อัปเดตข้อมูลรถทั้งหมดลงใน Database"""
    if not isinstance(vehicles_list, list):
        logger.warning(f"save_vehicles_to_db received non-list: {type(vehicles_list)}")
        return

    max_retries = 3
    for attempt in range(max_retries):
        db = SessionLocal()
        try:
            db.query(Vehicle).delete()
            db.flush()

            for idx, v in enumerate(vehicles_list):
                if not isinstance(v, dict):
                    continue
                try:
                    v_id = int(v.get("id") if v.get("id") is not None else (idx + 1))
                except (ValueError, TypeError):
                    v_id = idx + 1

                name = str(v.get("name") if v.get("name") is not None else f"รถคันที่ {v_id}")
                plate = str(v.get("plate") or "")
                driver = str(v.get("driver") or "")
                line_user_id = str(v.get("line_user_id") or "")

                try:
                    cap_val = v.get("capacity")
                    capacity = float(cap_val) if (cap_val is not None and cap_val != "") else 3750.0
                except (ValueError, TypeError):
                    capacity = 3750.0

                raw_act = v.get("active")
                active = 1 if (raw_act is True or raw_act == 1 or raw_act == "1" or raw_act is None or str(raw_act).lower() == "true") else 0

                try:
                    max_volume_cbm = float(v.get("max_volume_cbm") or 0)
                except (ValueError, TypeError):
                    max_volume_cbm = 0.0
                try:
                    max_boxes = int(v.get("max_boxes") or 0)
                except (ValueError, TypeError):
                    max_boxes = 0
                try:
                    max_stops = int(v.get("max_stops") or 0)
                except (ValueError, TypeError):
                    max_stops = 0

                vehicle = Vehicle(
                    id=v_id,
                    name=name,
                    plate=plate,
                    driver=driver,
                    capacity=capacity,
                    max_volume_cbm=max_volume_cbm,
                    max_boxes=max_boxes,
                    max_stops=max_stops,
                    line_user_id=line_user_id,
                    active=bool(active)
                )
                db.add(vehicle)

            db.commit()
            logger.info(f"บันทึกข้อมูลรถ {len(vehicles_list)} คันลงใน Database เรียบร้อยแล้ว")
            return
        except OperationalError as err:
            db.rollback()
            if "locked" in str(err).lower() and attempt < max_retries - 1:
                logger.warning(f"Database locked, retrying save_vehicles_to_db (attempt {attempt + 1}/{max_retries})...")
                time.sleep(0.2)
                continue
            logger.error(f"Error in save_vehicles_to_db: {err}", exc_info=True)
            raise err
        except Exception as err:
            db.rollback()
            logger.error(f"Error in save_vehicles_to_db: {err}", exc_info=True)
            raise err
        finally:
            db.close()


def get_vehicles_from_db() -> list[dict]:
    """ดึงข้อมูลรถทั้งหมดจาก Database"""
    db = SessionLocal()
    try:
        vehicles = db.query(Vehicle).order_by(Vehicle.id.asc()).all()

        if not vehicles:
            return []

        result = []
        for v in vehicles:
            r = {
                "id": v.id,
                "name": v.name,
                "plate": v.plate,
                "driver": v.driver,
                "capacity": v.capacity,
                "max_volume_cbm": v.max_volume_cbm or 0,
                "max_boxes": v.max_boxes or 0,
                "max_stops": v.max_stops or 0,
                "line_user_id": v.line_user_id or "",
                "active": bool(v.active)
            }
            result.append(r)
        return result
    finally:
        db.close()


def delete_vehicle_from_db(vehicle_id: int):
    """ลบรถจาก Database ตาม ID"""
    db = SessionLocal()
    try:
        vehicle = db.query(Vehicle).filter(Vehicle.id == vehicle_id).first()
        if vehicle:
            db.delete(vehicle)
            db.commit()
            logger.info(f"ลบรถ ID #{vehicle_id} จาก Database เรียบร้อยแล้ว")
        else:
            logger.warning(f"ไม่พบรถ ID #{vehicle_id} ใน Database")
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting vehicle: {e}")
        raise
    finally:
        db.close()
