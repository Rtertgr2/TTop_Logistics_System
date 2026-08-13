#!/usr/bin/env python3
"""
Script สำหรับย้ายข้อมูลจาก SQLite ไป PostgreSQL
ใช้: python migrate_sqlite_to_postgres.py
"""

import sqlite3
import os
import sys
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# เพิ่ม path ของโปรเจกต์
sys.path.insert(0, os.path.dirname(__file__))

from database.models import Base, Order, OrderItem, Vehicle, RoutePlan, RouteDetail, CustomerLocation

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "data", "logistics.db")
POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://logistics:logistics@db:5432/logistics")


def migrate():
    """ย้ายข้อมูลจาก SQLite ไป PostgreSQL"""

    if not os.path.exists(SQLITE_PATH):
        print(f"❌ ไม่พบ SQLite database: {SQLITE_PATH}")
        return

    print(f"📖 กำลังอ่านข้อมูลจาก SQLite: {SQLITE_PATH}")

    # เชื่อมต่อ SQLite
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()

    # เชื่อมต่อ PostgreSQL
    print(f"🐘 กำลังเชื่อมต่อ PostgreSQL: {POSTGRES_URL}")
    engine = create_engine(POSTGRES_URL)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    pg_session = Session()

    try:
        # 1. ย้าย Orders
        print("\n📦 กำลังย้าย Orders...")
        sqlite_cursor.execute("SELECT * FROM orders")
        orders = sqlite_cursor.fetchall()
        order_id_map = {}  # old_id -> new_id

        for row in orders:
            order = Order(
                order_number=row["order_number"],
                customer=row["customer"],
                address=row["address"],
                weight=row["weight"],
                source_file=row["source_file"],
                lat=row["lat"],
                lng=row["lng"],
                raw_lat=row["raw_lat"],
                raw_lng=row["raw_lng"],
                verified_lat=row["verified_lat"],
                verified_lng=row["verified_lng"],
                confidence_score=row["confidence_score"],
                geocode_provider=row["geocode_provider"],
                is_verified=bool(row["is_verified"]),
                verified_by=row["verified_by"],
                verified_at=datetime.fromisoformat(row["verified_at"]) if row["verified_at"] else None,
                zone=row["zone"],
                products_json=row["products_json"],
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow()
            )
            pg_session.add(order)
            pg_session.flush()
            order_id_map[row["id"]] = order.id

        print(f"   ✅ ย้าย {len(orders)} orders")

        # 2. ย้าย Order Items
        print("\n📋 กำลังย้าย Order Items...")
        sqlite_cursor.execute("SELECT * FROM order_items")
        items = sqlite_cursor.fetchall()

        for row in items:
            new_order_id = order_id_map.get(row["order_id"])
            if new_order_id:
                item = OrderItem(
                    order_id=new_order_id,
                    product_code=row["product_code"],
                    product_name=row["product_name"],
                    quantity=row["quantity"],
                    unit=row["unit"],
                    price=row["price"],
                    total=row["total"]
                )
                pg_session.add(item)

        print(f"   ✅ ย้าย {len(items)} order items")

        # 3. ย้าย Vehicles
        print("\n🚚 กำลังย้าย Vehicles...")
        sqlite_cursor.execute("SELECT * FROM vehicles")
        vehicles = sqlite_cursor.fetchall()

        for row in vehicles:
            vehicle = Vehicle(
                id=row["id"],
                name=row["name"],
                plate=row["plate"],
                driver=row["driver"],
                capacity=row["capacity"],
                max_volume_cbm=row["max_volume_cbm"],
                max_boxes=row["max_boxes"],
                max_stops=row["max_stops"],
                active=bool(row["active"])
            )
            pg_session.add(vehicle)

        print(f"   ✅ ย้าย {len(vehicles)} vehicles")

        # 4. ย้าย Route Plans
        print("\n🗺️ กำลังย้าย Route Plans...")
        sqlite_cursor.execute("SELECT * FROM route_plans")
        plans = sqlite_cursor.fetchall()
        plan_id_map = {}

        for row in plans:
            plan = RoutePlan(
                plan_date=datetime.fromisoformat(row["plan_date"]) if row["plan_date"] else datetime.utcnow(),
                total_orders=row["total_orders"],
                total_vehicles=row["total_vehicles"],
                depot_address=row["depot_address"],
                created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else datetime.utcnow()
            )
            pg_session.add(plan)
            pg_session.flush()
            plan_id_map[row["id"]] = plan.id

        print(f"   ✅ ย้าย {len(plans)} route plans")

        # 5. ย้าย Route Details
        print("\n📍 กำลังย้าย Route Details...")
        sqlite_cursor.execute("SELECT * FROM route_details")
        details = sqlite_cursor.fetchall()

        for row in details:
            new_plan_id = plan_id_map.get(row["plan_id"])
            if new_plan_id:
                detail = RouteDetail(
                    plan_id=new_plan_id,
                    vehicle_id=row["vehicle_id"],
                    plate=row["plate"],
                    driver=row["driver"],
                    total_weight=row["total_weight"],
                    google_maps_link=row["google_maps_link"],
                    stops_json=row["stops_json"]
                )
                pg_session.add(detail)

        print(f"   ✅ ย้าย {len(details)} route details")

        # 6. ย้าย Customer Locations
        print("\n📍 กำลังย้าย Customer Locations...")
        sqlite_cursor.execute("SELECT * FROM customer_locations")
        locations = sqlite_cursor.fetchall()

        for row in locations:
            location = CustomerLocation(
                customer_key=row["customer_key"],
                address_key=row["address_key"],
                lat=row["lat"],
                lng=row["lng"],
                formatted_address=row["formatted_address"],
                confidence_score=row["confidence_score"],
                updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else datetime.utcnow()
            )
            pg_session.add(location)

        print(f"   ✅ ย้าย {len(locations)} customer locations")

        # Commit
        pg_session.commit()
        print("\n✅ ย้ายข้อมูลเสร็จสมบูรณ์!")

    except Exception as e:
        pg_session.rollback()
        print(f"\n❌ เกิดข้อผิดพลาด: {e}")
        raise
    finally:
        pg_session.close()
        sqlite_conn.close()


if __name__ == "__main__":
    print("🔄 เริ่มย้ายข้อมูล SQLite → PostgreSQL")
    print("=" * 50)
    migrate()
    print("=" * 50)
    print("✅ เสร็จสิ้น!")
