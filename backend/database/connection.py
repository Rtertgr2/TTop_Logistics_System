"""Database connection, engine, session, and initialization."""

import logging
import os
import sys
import time
from datetime import UTC, datetime

from dotenv import load_dotenv
from sqlalchemy import DDL, create_engine, text
from sqlalchemy.orm import sessionmaker

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

from database.models import Base

load_dotenv()

logger = logging.getLogger(__name__)

PRODUCTION_MODE = os.getenv("PRODUCTION_MODE", "false").lower() == "true"

_DEFAULT_DB_URL = "postgresql://logistics:logistics@db:5432/logistics"
DATABASE_URL = os.getenv("DATABASE_URL", _DEFAULT_DB_URL)

if PRODUCTION_MODE and DATABASE_URL == _DEFAULT_DB_URL:
    logger.critical("FATAL: DATABASE_URL must be set in production! Exiting.")
    sys.exit(1)

if DATABASE_URL == _DEFAULT_DB_URL:
    logger.warning("Using default DATABASE_URL credentials — set DATABASE_URL env var!")

_BUSINESS_TZ = os.getenv("BUSINESS_TIMEZONE", "Asia/Bangkok")


def _business_today() -> tuple:
    """คืน (today_date, tz_name) ตาม BUSINESS_TIMEZONE — ป้องกันข้อมูลหายตอนเที่ยงคืน UTC (vs เวลาไทย)"""
    tz_name = _BUSINESS_TZ
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(tz_name)).date(), tz_name
        except Exception:
            logger.warning(
                f"Invalid BUSINESS_TIMEZONE={tz_name!r}, falling back to UTC"
            )
    return datetime.now(UTC).date(), "UTC"


engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _record_db_metric(operation: str, table: str, start_time: float, success: bool):
    """Record DB operation metrics (safe import)"""
    try:
        from metrics import record_db_operation

        duration = time.time() - start_time
        record_db_operation(operation, table, duration, success)
    except Exception:
        logger.warning("Failed to record DB metric")


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
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except Exception as e:
        error_msg = "Database connection failed" if PRODUCTION_MODE else str(e)
        return {
            "status": "disconnected",
            "database": "postgresql",
            "error": error_msg,
            "timestamp": datetime.now(UTC).isoformat(),
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

    logger.info(
        "Database tables ready (vehicles ไม่ถูก seed — เริ่มต้นว่าง รอ admin กรอกผ่าน UI)"
    )


def _migrate_columns():
    """เพิ่มคอลัมน์ที่อาจยังไม่มีในตารางเดิม (รองรับ SQLite + Postgres)"""
    from sqlalchemy import inspect as sa_inspect

    migs = [
        ("vehicles", "line_user_id", "VARCHAR(200)"),
        ("order_items", "item_weight", "FLOAT"),
        ("orders", "delivery_date", "VARCHAR(10)"),
        ("orders", "booking_status", "VARCHAR(50)"),
        ("users", "email", "VARCHAR(200)"),
        ("users", "phone", "VARCHAR(50)"),
        ("users", "department", "VARCHAR(100)"),
        ("users", "position", "VARCHAR(100)"),
        ("users", "updated_at", "TIMESTAMP"),
        ("users", "consent_given", "BOOLEAN"),
        ("users", "consent_date", "TIMESTAMP"),
        ("users", "privacy_policy_version", "VARCHAR(20)"),
    ]
    db = SessionLocal()
    try:
        inspector = sa_inspect(engine)
        for table, column, col_type in migs:
            try:
                existing = {c["name"] for c in inspector.get_columns(table)}
            except Exception:
                logger.warning(f"Failed to inspect table {table}")
                continue
            if column in existing:
                continue
            # col_type มาจาก whitelist ที่ hardcode ด้านบน (ไม่ใช่ user input) จึงปลอดภัย
            db.execute(DDL(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
            db.commit()
            logger.info(f"Migration: เพิ่มคอลัมน์ {column} ในตาราง {table}")

        # สร้างตาราง audit_logs หากยังไม่มี
        try:
            db.execute(
                text("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    username VARCHAR(100) NOT NULL,
                    action VARCHAR(50) NOT NULL,
                    target_user VARCHAR(100) DEFAULT '',
                    details TEXT DEFAULT '',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            )
            db.commit()
            logger.info("Migration: สร้างตาราง audit_logs เรียบร้อย")
        except Exception as e:
            db.rollback()
            logger.warning(f"audit_logs migration skipped: {e}")
    except Exception:
        db.rollback()
        logger.exception("Migration error")
    finally:
        db.close()
