#!/usr/bin/env python3
"""
Migration script: เพิ่มตารางใหม่ 6 ตารางสำหรับ REQ-1,2,3,4
- drivers
- vehicle_loads
- stop_status_history
- item_deliveries
- route_transfers
- vehicle_locations

ใช้: python database/migrate_add_tables.py
"""

import os
import sys
import logging

# เพิ่ม path ของโปรเจกต์
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

from database.models import Base, Driver, VehicleLoad, StopStatusHistory, ItemDelivery, RouteTransfer, VehicleLocation

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://logistics:logistics@db:5432/logistics")


def migrate():
    """เพิ่มตารางใหม่"""
    logger.info(f"Connecting to database: {DATABASE_URL.split('@')[-1]}")
    engine = create_engine(DATABASE_URL)

    # สร้างตารางใหม่ทั้งหมด
    logger.info("Creating new tables...")
    Base.metadata.create_all(bind=engine, tables=[
        Driver.__table__,
        VehicleLoad.__table__,
        StopStatusHistory.__table__,
        ItemDelivery.__table__,
        RouteTransfer.__table__,
        VehicleLocation.__table__,
    ])

    logger.info("✅ Migration completed successfully!")
    logger.info("New tables created:")
    logger.info("  - drivers")
    logger.info("  - vehicle_loads")
    logger.info("  - stop_status_history")
    logger.info("  - item_deliveries")
    logger.info("  - route_transfers")
    logger.info("  - vehicle_locations")


if __name__ == "__main__":
    logger.info("Starting migration: Add missing tables")
    logger.info("=" * 50)
    try:
        migrate()
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)
    logger.info("=" * 50)
    logger.info("Migration completed!")
