"""
Structured Logging Configuration
JSON-formatted logs for production monitoring
"""

import json
import logging
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging"""

    def format(self, record):
        log_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # เพิ่ม exception info ถ้ามี
        if record.exc_info and record.exc_info[1]:
            log_data["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }

        # เพิ่ม extra fields
        if hasattr(record, "extra_data"):
            log_data["extra"] = record.extra_data

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(log_level: str = "INFO", json_format: bool = False):
    """ตั้งค่า logging"""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # ลบ handlers เดิม
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # สร้าง console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.addHandler(console_handler)

    # ตั้งค่า log level สำหรับ libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured: level={log_level}, json={json_format}")


def log_api_request(method: str, path: str, status_code: int, duration_ms: float):
    """Log API request"""
    logger = logging.getLogger("api")
    logger.info(f"{method} {path} - {status_code} ({duration_ms:.1f}ms)")


def log_database_operation(
    operation: str, table: str, duration_ms: float, success: bool
):
    """Log database operation"""
    logger = logging.getLogger("database")
    status = "success" if success else "failed"
    logger.info(f"{operation} {table} - {status} ({duration_ms:.1f}ms)")


def log_external_api_call(
    api_name: str, endpoint: str, status_code: int, duration_ms: float
):
    """Log external API call"""
    logger = logging.getLogger("external_api")
    logger.info(f"{api_name} {endpoint} - {status_code} ({duration_ms:.1f}ms)")
