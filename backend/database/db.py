import os
import json
import logging
import time
from datetime import datetime, timezone
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError
from dotenv import load_dotenv

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

from database.models import Base, Order, OrderItem, Vehicle, RoutePlan, RouteDetail, CustomerLocation, Driver, VehicleLoad, StopStatusHistory, ItemDelivery, RouteTransfer, VehicleLocation

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://logistics:logistics@db:5432/logistics")

_BUSINESS_TZ = os.getenv("BUSINESS_TIMEZONE", "Asia/Bangkok")


def _business_today() -> tuple:
    """คืน (today_date, tz_name) ตาม BUSINESS_TIMEZONE — ป้องกันข้อมูลหายตอนเที่ยงคืน UTC (vs เวลาไทย)"""
    tz_name = _BUSINESS_TZ
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(tz_name)).date(), tz_name
        except Exception:
            logger.warning(f"Invalid BUSINESS_TIMEZONE={tz_name!r}, falling back to UTC")
    return datetime.now(timezone.utc).date(), "UTC"

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _record_db_metric(operation: str, table: str, start_time: float, success: bool):
    """Record DB operation metrics (safe import)"""
    try:
        from metrics import record_db_operation
        duration = time.time() - start_time
        record_db_operation(operation, table, duration, success)
    except Exception:
        pass  # Never let metrics failure break DB operations


def get_db():
    """Dependency สำหรับ FastAPI — ใช้ session เดียวต่อ request"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """ตรวจสอบการเชื่อมต่อ Database"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database connection check failed: {e}")
        return False


def get_db_status() -> dict:
    """ดึงสถานะ Database สำหรับ health check"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        return {
            "status": "connected",
            "database": "postgresql",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "status": "disconnected",
            "database": "postgresql",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


def init_db():
    """สร้างตารางใน Database หากยังไม่มี + เพิ่มคอลัมน์ที่ขาดให้ตารางเดิม"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

    _migrate_columns()

    logger.info("Database tables ready (vehicles ไม่ถูก seed — เริ่มต้นว่าง รอ admin กรอกผ่าน UI)")


def _migrate_columns():
    """เพิ่มคอลัมน์ที่อาจยังไม่มีในตารางเดิม (รองรับ SQLite + Postgres)"""
    from sqlalchemy import inspect as sa_inspect

    migs = [
        ("vehicles", "line_user_id", "VARCHAR(200)"),
        ("order_items", "item_weight", "FLOAT"),
    ]
    db = SessionLocal()
    try:
        inspector = sa_inspect(engine)
        for table, column, col_type in migs:
            try:
                existing = {c["name"] for c in inspector.get_columns(table)}
            except Exception:
                continue
            if column in existing:
                continue
            db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            db.commit()
            logger.info(f"Migration: เพิ่มคอลัมน์ {column} ในตาราง {table}")
    except Exception as e:
        db.rollback()
        logger.error(f"Migration error: {e}", exc_info=True)
    finally:
        db.close()


def get_saved_customer_location(customer: str, address: str) -> dict | None:
    """ดึงพิกัดที่เคยยืนยันแล้วจากตาราง customer_locations"""
    if not customer and not address:
        return None

    db = SessionLocal()
    try:
        clean_key = (customer.strip() if customer else "") + "_" + (address.strip() if address else "")
        clean_key = clean_key.lower().replace(" ", "")

        location = db.query(CustomerLocation).filter(
            (CustomerLocation.customer_key == clean_key) |
            (CustomerLocation.address_key == clean_key)
        ).first()

        if location:
            return {
                "lat": location.lat,
                "lng": location.lng,
                "formatted_address": location.formatted_address,
                "confidence_score": location.confidence_score or 100.0,
                "geocode_provider": "database_memory",
                "is_verified": True
            }
        return None
    finally:
        db.close()


def save_customer_location(customer: str, address: str, lat: float, lng: float, formatted_address: str = "", confidence_score: float = 100.0, db=None) -> bool:
    """บันทึก/อัปเดตพิกัดลูกค้าลงตาราง customer_locations เพื่อใช้จำถาวร
    ถ้าส่ง db มา จะใช้ session เดียวกันกับ caller (ไม่ commit/close เอง)"""
    if not lat or not lng:
        return False

    clean_key = (customer.strip() if customer else "") + "_" + (address.strip() if address else "")
    clean_key = clean_key.lower().replace(" ", "")
    if len(clean_key) < 2:
        return False

    _owns_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        existing = db.query(CustomerLocation).filter(CustomerLocation.customer_key == clean_key).first()

        if existing:
            existing.lat = lat
            existing.lng = lng
            existing.formatted_address = formatted_address or address
            existing.confidence_score = confidence_score
            existing.updated_at = datetime.now(timezone.utc)
        else:
            location = CustomerLocation(
                customer_key=clean_key,
                address_key=clean_key,
                lat=lat,
                lng=lng,
                formatted_address=formatted_address or address,
                confidence_score=confidence_score,
                updated_at=datetime.now(timezone.utc)
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
        locations = db.query(CustomerLocation).order_by(CustomerLocation.updated_at.desc()).limit(limit).all()
        return [
            {
                "id": loc.id,
                "customer_key": loc.customer_key,
                "lat": loc.lat,
                "lng": loc.lng,
                "formatted_address": loc.formatted_address,
                "confidence_score": loc.confidence_score,
                "updated_at": loc.updated_at
            }
            for loc in locations
        ]
    finally:
        db.close()


def delete_customer_location(loc_id: int) -> bool:
    """ลบพิกัดความจำถาวรของลูกค้าตาม ID"""
    db = SessionLocal()
    try:
        location = db.query(CustomerLocation).filter(CustomerLocation.id == loc_id).first()
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
                created_at=datetime.now(timezone.utc)
            )
            db.add(db_order)
            db.flush()

            new_id = db_order.id
            order["id"] = new_id
            saved_ids.append(new_id)

            # บันทึกรายการสินค้าลง order_items
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
                        item_weight=p.get("item_weight", 0)  # น้ำหนักรวมจาก Product table
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


def update_order_location(order_id: int, lat: float, lng: float, verified_by: str = "user") -> bool:
    """อัปเดตและยืนยันพิกัดตำแหน่งจริงของออเดอร์ พร้อมเซฟเข้าความจำความแม่นยำถาวร"""
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
        order.verified_at = datetime.now(timezone.utc)

        # บันทึก location memory (ใช้ session เดียวกัน — atomic)
        save_customer_location(order.customer, order.address, lat, lng, f"Verified Location ({lat}, {lng})", 100.0, db=db)

        # อัปเดตพิกัดในแผนเส้นทางวันนี้ (stops_json) ที่อ้างอิงออเดอร์นี้ —
        # ป้องกันคนขับ/Excel ยังใช้พิกัดเก่าแม้ dispatcher จะแก้พิกัดแล้ว
        try:
            today, tz = _business_today()
            plan = db.query(RoutePlan).filter(
                text("DATE(plan_date AT TIME ZONE :tz) = :today")
            ).params(today=today, tz=tz).order_by(RoutePlan.id.desc()).first()
            if plan:
                details = db.query(RouteDetail).filter(RouteDetail.plan_id == plan.id).all()
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
        logger.info(f"Updated location for Order #{order_id} => ({lat}, {lng}) by {verified_by}")
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating order location: {e}")
        return False
    finally:
        db.close()


def save_route_plan(routes: list[dict], depot: dict = None) -> int:
    """บันทึกผลการจัดคิวรถ (Route Plan) ลง Database"""
    db = SessionLocal()
    start_time = time.time()
    try:
        plan_date = datetime.now(timezone.utc)
        total_orders = sum(len(r.get("stops", [])) for r in routes)
        total_vehicles = len(routes)
        depot_addr = depot.get("address", "") if depot else ""

        plan = RoutePlan(
            plan_date=plan_date,
            total_orders=total_orders,
            total_vehicles=total_vehicles,
            depot_address=depot_addr
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
                stops_json=stops_json
            )
            db.add(detail)

        db.commit()
        _record_db_metric("save", "route_plans", start_time, True)
        logger.info(f"Saved Route Plan #{plan_id} with {len(routes)} vehicles to Database")
        return plan_id
    except Exception as e:
        db.rollback()
        _record_db_metric("save", "route_plans", start_time, False)
        logger.error(f"Error saving route plan: {e}")
        raise
    finally:
        db.close()


def get_today_orders() -> list[dict]:
    """ดึงรายการออเดอร์เฉพาะวันปัจจุบัน (ตัดรอบเที่ยงคืนตาม BUSINESS_TIMEZONE)"""
    db = SessionLocal()
    try:
        today, tz = _business_today()
        orders = db.query(Order).filter(
            text("DATE(created_at AT TIME ZONE :tz) = :today")
        ).params(today=today, tz=tz).order_by(Order.id.desc()).all()

        result = []
        for order in orders:
            r = _order_to_dict(order)
            result.append(r)
        return result
    finally:
        db.close()


def get_today_active_routes() -> list[dict]:
    """ดึงแผนการเดินรถล่าสุดของวันนี้ (ตัดรอบเที่ยงคืนตาม BUSINESS_TIMEZONE)"""
    db = SessionLocal()
    try:
        today, tz = _business_today()
        plan = db.query(RoutePlan).filter(
            text("DATE(plan_date AT TIME ZONE :tz) = :today")
        ).params(today=today, tz=tz).order_by(RoutePlan.id.desc()).first()

        if not plan:
            return []

        details = db.query(RouteDetail).filter(RouteDetail.plan_id == plan.id).order_by(RouteDetail.vehicle_id.asc()).all()
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
                "stops": json.loads(d.stops_json) if d.stops_json else []
            }
            routes.append(rd)
        return routes
    finally:
        db.close()


def get_all_orders(limit: int = 100) -> list[dict]:
    """ดึงรายการออเดอร์ล่าสุดจาก Database"""
    db = SessionLocal()
    try:
        orders = db.query(Order).order_by(Order.id.desc()).limit(limit).all()
        result = []
        for order in orders:
            r = _order_to_dict(order)
            result.append(r)
        return result
    finally:
        db.close()


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
        "created_at": order.created_at
    }
    if r.get("products_json"):
        try:
            r["products"] = json.loads(r["products_json"])
        except Exception:
            r["products"] = []
    return r


def get_route_history(limit: int = 20) -> list[dict]:
    """ดึงประวัติการจัดคิวรถย้อนหลัง"""
    db = SessionLocal()
    try:
        plans = db.query(RoutePlan).order_by(RoutePlan.id.desc()).limit(limit).all()
        result = []
        for plan in plans:
            p = {
                "id": plan.id,
                "plan_date": plan.plan_date,
                "total_orders": plan.total_orders,
                "total_vehicles": plan.total_vehicles,
                "depot_address": plan.depot_address,
                "created_at": plan.created_at
            }

            details = db.query(RouteDetail).filter(RouteDetail.plan_id == plan.id).order_by(RouteDetail.vehicle_id.asc()).all()
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
                    "stops": json.loads(d.stops_json) if d.stops_json else []
                }
                routes.append(rd)
            p["routes"] = routes
            result.append(p)
        return result
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

        # Reset sequences (เฉพาะตารางที่ล้าง — รถคงเดิม ไม่รีเซ็ต)
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

                # ขีดจำกัดเพิ่มเติม (volume / กล่อง / จำนวนจุดจอด)
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


# ── Delivery Status Functions ─────────────────────────────────────

def update_stop_status(route_id: int, stop_id: int, new_status: str, updated_by: str = "driver", note: str = "", order_id: int = None) -> dict:
    """อัปเดตสถานะของ stop ใน route + บันทึก history"""
    from services.delivery_status import validate_transition

    db = SessionLocal()
    start_time = time.time()
    try:
        # ดึง route detail
        route = db.query(RouteDetail).filter(RouteDetail.id == route_id).first()
        if not route:
            return {"success": False, "error": "ไม่พบเส้นทาง"}

        stops = json.loads(route.stops_json) if route.stops_json else []

        # หา stop ที่ต้องการ
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

        # Validate transition
        if not validate_transition(current_status, new_status):
            return {
                "success": False,
                "error": f"ไม่สามารถเปลี่ยนสถานะจาก {current_status} เป็น {new_status} ได้"
            }

        # Update stop status
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

        # Save back to route
        route.stops_json = json.dumps(stops, ensure_ascii=False)

        # Record history
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
    db = SessionLocal()
    try:
        today, tz = _business_today()
        plan = db.query(RoutePlan).filter(
            text("DATE(plan_date AT TIME ZONE :tz) = :today")
        ).params(today=today, tz=tz).order_by(RoutePlan.id.desc()).first()

        if not plan:
            return None

        details = db.query(RouteDetail).filter(
            RouteDetail.plan_id == plan.id,
            RouteDetail.driver == driver_name
        ).all()

        if not details:
            return None

        # รวมทุก RouteDetail ของคนขับ (รองรับโหมด clustered ที่มีหลายโซนรวมกัน)
        merged_stops = []
        primary = details[0]
        total_weight = 0.0
        for d in details:
            stops = json.loads(d.stops_json) if d.stops_json else []
            merged_stops.extend(stops)
            total_weight += float(d.total_weight or 0)

        from services.delivery_status import calculate_delivery_summary
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
            # ดึง ordered_qty จาก order_item
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

