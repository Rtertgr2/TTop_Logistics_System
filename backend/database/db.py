import sqlite3
import os
import json
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "logistics.db")


def get_connection():
    """เชื่อมต่อกับไฟล์ SQLite Database พร้อมเปิดใช้งาน timeout=30.0, busy_timeout และ Performance PRAGMAs"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA cache_size = -64000")
    conn.execute("PRAGMA temp_store = MEMORY")
    return conn


def init_db():
    """สร้างตารางใน Database หากยังไม่มี"""
    conn = get_connection()
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except Exception as e:
        logger.warning(f"Could not set journal_mode to WAL: {e}")

    cursor = conn.cursor()

    # ตารางออเดอร์ (Orders)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT,
            customer TEXT NOT NULL,
            address TEXT NOT NULL,
            weight REAL DEFAULT 0,
            source_file TEXT,
            lat REAL,
            lng REAL,
            raw_lat REAL,
            raw_lng REAL,
            verified_lat REAL,
            verified_lng REAL,
            confidence_score REAL DEFAULT 0,
            geocode_provider TEXT DEFAULT 'none',
            is_verified INTEGER DEFAULT 0,
            verified_by TEXT,
            verified_at TEXT,
            zone TEXT,
            products_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Auto migration for existing databases
    existing_cols = [r[1] for r in cursor.execute("PRAGMA table_info(orders)").fetchall()]
    new_cols = [
        ("raw_lat", "REAL"), ("raw_lng", "REAL"),
        ("verified_lat", "REAL"), ("verified_lng", "REAL"),
        ("confidence_score", "REAL DEFAULT 0"),
        ("geocode_provider", "TEXT DEFAULT 'none'"),
        ("is_verified", "INTEGER DEFAULT 0"),
        ("verified_by", "TEXT"), ("verified_at", "TEXT")
    ]
    for col_name, col_type in new_cols:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")

    # ตารางแผนจัดส่ง (Route Plans)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS route_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_date TEXT NOT NULL,
            total_orders INTEGER DEFAULT 0,
            total_vehicles INTEGER DEFAULT 0,
            depot_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ตารางรายละเอียดเส้นทาง (Route Details)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS route_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL,
            vehicle_id INTEGER NOT NULL,
            plate TEXT,
            driver TEXT,
            total_weight REAL,
            google_maps_link TEXT,
            stops_json TEXT,
            FOREIGN KEY (plan_id) REFERENCES route_plans (id) ON DELETE CASCADE
        )
    """)

    # ตารางยานพาหนะ (Vehicles)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY,
            name TEXT,
            plate TEXT NOT NULL,
            driver TEXT,
            capacity REAL DEFAULT 5000,
            active INTEGER DEFAULT 1
        )
    """)
    existing_veh_cols = [r[1] for r in cursor.execute("PRAGMA table_info(vehicles)").fetchall()]
    if "name" not in existing_veh_cols:
        cursor.execute("ALTER TABLE vehicles ADD COLUMN name TEXT")
    if "active" not in existing_veh_cols:
        cursor.execute("ALTER TABLE vehicles ADD COLUMN active INTEGER DEFAULT 1")

    # ตารางจดจำพิกัดลูกค้าที่เคยยืนยันแล้ว (Persistent Customer Location Memory)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customer_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_key TEXT UNIQUE NOT NULL,
            address_key TEXT,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            formatted_address TEXT,
            confidence_score REAL DEFAULT 100.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ⚡ High-performance Database Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_route_plans_plan_date ON route_plans(plan_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_route_details_plan_id ON route_details(plan_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_vehicles_active ON vehicles(active);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_customer_locations_key ON customer_locations(customer_key);")

    conn.commit()
    conn.close()
    logger.info(f"Database initialized with performance indexes at {DB_PATH}")


def get_saved_customer_location(customer: str, address: str) -> dict | None:
    """ดึงพิกัดที่เคยยืนยันแล้วจากตาราง customer_locations"""
    if not customer and not address:
        return None

    conn = get_connection()
    cursor = conn.cursor()
    
    clean_key = (customer.strip() if customer else "") + "_" + (address.strip() if address else "")
    clean_key = clean_key.lower().replace(" ", "")

    cursor.execute("""
        SELECT lat, lng, formatted_address, confidence_score
        FROM customer_locations
        WHERE customer_key = ? OR address_key = ?
    """, (clean_key, clean_key))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "lat": row["lat"],
            "lng": row["lng"],
            "formatted_address": row["formatted_address"],
            "confidence_score": row["confidence_score"] or 100.0,
            "geocode_provider": "database_memory",
            "is_verified": True
        }
    return None


def save_customer_location(customer: str, address: str, lat: float, lng: float, formatted_address: str = "", confidence_score: float = 100.0) -> bool:
    """บันทึก/อัปเดตพิกัดลูกค้าลงตาราง customer_locations เพื่อใช้จำถาวร"""
    if not lat or not lng:
        return False

    clean_key = (customer.strip() if customer else "") + "_" + (address.strip() if address else "")
    clean_key = clean_key.lower().replace(" ", "")
    if len(clean_key) < 2:
        return False

    conn = get_connection()
    cursor = conn.cursor()
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO customer_locations (customer_key, address_key, lat, lng, formatted_address, confidence_score, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(customer_key) DO UPDATE SET
            lat = excluded.lat,
            lng = excluded.lng,
            formatted_address = excluded.formatted_address,
            confidence_score = excluded.confidence_score,
            updated_at = excluded.updated_at
    """, (clean_key, clean_key, lat, lng, formatted_address or address, confidence_score, updated_at))

    conn.commit()
    conn.close()
    logger.info(f"Saved location memory for key '{clean_key}' => ({lat}, {lng})")
    return True


def get_all_customer_locations(limit: int = 200) -> list[dict]:
    """ดึงข้อมูลพิกัดความจำถาวรของลูกค้าทั้งหมด"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, customer_key, lat, lng, formatted_address, confidence_score, updated_at
        FROM customer_locations
        ORDER BY updated_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_customer_location(loc_id: int) -> bool:
    """ลบพิกัดความจำถาวรของลูกค้าตาม ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM customer_locations WHERE id = ?", (loc_id,))
    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def save_orders(orders: list[dict]) -> list[int]:
    """บันทึกรายการออเดอร์ลง Database"""
    if not orders:
        return []

    conn = get_connection()
    cursor = conn.cursor()
    saved_ids = []

    for order in orders:
        products_json = json.dumps(order.get("products", []), ensure_ascii=False)
        lat = order.get("lat")
        lng = order.get("lng")
        cursor.execute("""
            INSERT INTO orders (
                order_number, customer, address, weight, source_file, 
                lat, lng, raw_lat, raw_lng, verified_lat, verified_lng,
                confidence_score, geocode_provider, is_verified, verified_by, verified_at,
                zone, products_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order.get("order_number"),
            order.get("customer", "ไม่ระบุ"),
            order.get("address", "ไม่ระบุ"),
            order.get("weight", 0),
            order.get("source_file"),
            lat,
            lng,
            order.get("raw_lat", lat),
            order.get("raw_lng", lng),
            order.get("verified_lat", lat),
            order.get("verified_lng", lng),
            order.get("confidence_score", 95.0),
            order.get("geocode_provider", "google"),
            1 if order.get("is_verified") else 0,
            order.get("verified_by"),
            order.get("verified_at"),
            order.get("zone"),
            products_json,
        ))
        new_id = cursor.lastrowid
        order["id"] = new_id
        saved_ids.append(new_id)

    conn.commit()
    conn.close()
    logger.info(f"Saved {len(saved_ids)} orders to Database")
    return saved_ids


def update_order_location(order_id: int, lat: float, lng: float, verified_by: str = "user") -> bool:
    """อัปเดตและยืนยันพิกัดตำแหน่งจริงของออเดอร์ พร้อมเซฟเข้าความจำความแม่นยำถาวร"""
    conn = get_connection()
    cursor = conn.cursor()
    verified_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("SELECT customer, address FROM orders WHERE id = ?", (order_id,))
    row = cursor.fetchone()

    cursor.execute("""
        UPDATE orders
        SET lat = ?, lng = ?, verified_lat = ?, verified_lng = ?,
            confidence_score = 100.0, is_verified = 1, verified_by = ?, verified_at = ?
        WHERE id = ?
    """, (lat, lng, lat, lng, verified_by, verified_at, order_id))

    affected = cursor.rowcount
    conn.commit()
    conn.close()

    if affected > 0 and row:
        try:
            cust = row["customer"]
            addr = row["address"]
            save_customer_location(cust, addr, lat, lng, f"Verified Location ({lat}, {lng})", 100.0)
        except Exception as e:
            logger.warning(f"Error auto-saving location memory in update_order_location: {e}")

    logger.info(f"Updated location for Order #{order_id} => ({lat}, {lng}) by {verified_by}")
    return affected > 0


def save_route_plan(routes: list[dict], depot: dict = None) -> int:
    """บันทึกผลการจัดคิวรถ (Route Plan) ลง Database"""
    conn = get_connection()
    cursor = conn.cursor()

    plan_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_orders = sum(len(r.get("stops", [])) for r in routes)
    total_vehicles = len(routes)
    depot_addr = depot.get("address", "") if depot else ""

    cursor.execute("""
        INSERT INTO route_plans (plan_date, total_orders, total_vehicles, depot_address)
        VALUES (?, ?, ?, ?)
    """, (plan_date, total_orders, total_vehicles, depot_addr))

    plan_id = cursor.lastrowid

    for route in routes:
        stops_json = json.dumps(route.get("stops", []), ensure_ascii=False)
        cursor.execute("""
            INSERT INTO route_details (plan_id, vehicle_id, plate, driver, total_weight, google_maps_link, stops_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            plan_id,
            route.get("vehicle_id"),
            route.get("plate"),
            route.get("driver"),
            route.get("total_weight"),
            route.get("google_maps_link"),
            stops_json,
        ))

    conn.commit()
    conn.close()
    logger.info(f"Saved Route Plan #{plan_id} with {len(routes)} vehicles to Database")
    return plan_id


def get_today_orders() -> list[dict]:
    """ดึงรายการออเดอร์เฉพาะวันปัจจุบัน (ตัดรอบเที่ยงคืน)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM orders 
        WHERE date(created_at, 'localtime') = date('now', 'localtime')
        ORDER BY id DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        r = dict(row)
        if r.get("products_json"):
            try:
                r["products"] = json.loads(r["products_json"])
            except Exception:
                r["products"] = []
        result.append(r)
    return result


def get_today_active_routes() -> list[dict]:
    """ดึงแผนการเดินรถล่าสุดของวันนี้ (ตัดรอบเที่ยงคืน)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM route_plans 
        WHERE date(plan_date, 'localtime') = date('now', 'localtime')
        ORDER BY id DESC LIMIT 1
    """)
    plan_row = cursor.fetchone()
    if not plan_row:
        conn.close()
        return []

    plan_id = plan_row["id"]
    cursor.execute("""
        SELECT * FROM route_details WHERE plan_id = ? ORDER BY vehicle_id ASC
    """, (plan_id,))
    details_rows = cursor.fetchall()
    routes = []
    for d in details_rows:
        rd = dict(d)
        if rd.get("stops_json"):
            try:
                rd["stops"] = json.loads(rd["stops_json"])
            except Exception:
                rd["stops"] = []
        routes.append(rd)

    conn.close()
    return routes


def get_all_orders(limit: int = 100) -> list[dict]:
    """ดึงรายการออเดอร์ล่าสุดจาก Database"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        r = dict(row)
        if r.get("products_json"):
            try:
                r["products"] = json.loads(r["products_json"])
            except Exception:
                r["products"] = []
        result.append(r)
    return result


def get_route_history(limit: int = 20) -> list[dict]:
    """ดึงประวัติการจัดคิวรถย้อนหลัง"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM route_plans ORDER BY id DESC LIMIT ?
    """, (limit,))
    plans = [dict(row) for row in cursor.fetchall()]

    for plan in plans:
        cursor.execute("""
            SELECT * FROM route_details WHERE plan_id = ? ORDER BY vehicle_id ASC
        """, (plan["id"],))
        details_rows = cursor.fetchall()
        routes = []
        for d in details_rows:
            rd = dict(d)
            if rd.get("stops_json"):
                try:
                    rd["stops"] = json.loads(rd["stops_json"])
                except Exception:
                    rd["stops"] = []
            routes.append(rd)
        plan["routes"] = routes

    conn.close()
    return plans


def clear_all_data():
    """ลบข้อมูลออเดอร์ ประวัติแผนจัดส่ง และรถขนส่งทั้งหมดใน Database พร้อมรีเซ็ต AutoIncrement ID ให้เริ่มนับ 1 ใหม่"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM orders")
    cursor.execute("DELETE FROM route_plans")
    cursor.execute("DELETE FROM route_details")
    cursor.execute("DELETE FROM vehicles")
    try:
        cursor.execute("DELETE FROM sqlite_sequence")
    except Exception as e:
        logger.warning(f"Could not reset sqlite_sequence: {e}")
    conn.commit()
    conn.close()

    save_vehicles_to_db(INITIAL_VEHICLES)
    logger.info("ล้างข้อมูลทั้งหมดใน Database และรีเซ็ต ID ให้เริ่มนับ 1 ใหม่เรียบร้อยแล้ว")


INITIAL_VEHICLES = [
    {"id": 1, "name": "รถคันที่ 1 (รถใหญ่ 3.75 ตัน)", "plate": "กข 1234", "capacity": 3750, "driver": "สมชาย", "active": True},
    {"id": 2, "name": "รถคันที่ 2 (รถกลาง 1.8 - 1.9 ตัน)", "plate": "กข 5678", "capacity": 1900, "driver": "สมศักดิ์", "active": True},
    {"id": 3, "name": "รถคันที่ 3 (รถกลาง 1.95 - 2.24 ตัน)", "plate": "กข 9012", "capacity": 2240, "driver": "สมบูรณ์", "active": True},
    {"id": 4, "name": "รถคันที่ 4 (รถใหญ่ 3.75 ตัน)", "plate": "กข 3456", "capacity": 3750, "driver": "สมเดช", "active": True},
]


def save_vehicles_to_db(vehicles_list: list[dict]):
    """บันทึก/อัปเดตข้อมูลรถทั้งหมดลงใน SQLite Database"""
    if not isinstance(vehicles_list, list):
        logger.warning(f"save_vehicles_to_db received non-list: {type(vehicles_list)}")
        return

    max_retries = 3
    for attempt in range(max_retries):
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM vehicles")
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
                
                try:
                    cap_val = v.get("capacity")
                    capacity = float(cap_val) if (cap_val is not None and cap_val != "") else 3750.0
                except (ValueError, TypeError):
                    capacity = 3750.0

                raw_act = v.get("active")
                active = 1 if (raw_act is True or raw_act == 1 or raw_act == "1" or raw_act is None or str(raw_act).lower() == "true") else 0

                cursor.execute("""
                    INSERT INTO vehicles (id, name, plate, driver, capacity, active)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (v_id, name, plate, driver, capacity, active))
            conn.commit()
            logger.info(f"บันทึกข้อมูลรถ {len(vehicles_list)} คันลงใน SQLite เรียบร้อยแล้ว")
            return
        except sqlite3.OperationalError as err:
            conn.rollback()
            if "locked" in str(err).lower() and attempt < max_retries - 1:
                logger.warning(f"Database locked, retrying save_vehicles_to_db (attempt {attempt + 1}/{max_retries})...")
                time.sleep(0.2)
                continue
            logger.error(f"Error in save_vehicles_to_db: {err}", exc_info=True)
            raise err
        except Exception as err:
            conn.rollback()
            logger.error(f"Error in save_vehicles_to_db: {err}", exc_info=True)
            raise err
        finally:
            conn.close()


def get_vehicles_from_db() -> list[dict]:
    """ดึงข้อมูลรถทั้งหมดจาก SQLite Database (หากยังไม่มีจะทำการ Seed ข้อมูลเริ่มต้น)"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM vehicles ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        save_vehicles_to_db(INITIAL_VEHICLES)
        return INITIAL_VEHICLES

    result = []
    for row in rows:
        r = dict(row)
        r["active"] = bool(r.get("active", 1) == 1)
        result.append(r)
    return result


def delete_vehicle_from_db(vehicle_id: int):
    """ลบรถจาก SQLite Database ตาม ID"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))
    conn.commit()
    conn.close()
    logger.info(f"ลบรถ ID #{vehicle_id} จาก SQLite Database เรียบร้อยแล้ว")

