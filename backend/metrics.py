"""
Prometheus Metrics Module
Provides metrics for monitoring and alerting
"""

import logging
import re
import time

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = logging.getLogger(__name__)


def _normalize_path(path: str) -> str:
    """Normalize path for metrics — replace numeric IDs with placeholders"""
    path = re.sub(r"/\d+", "/{id}", path)
    return path


# ─── Metrics ──────────────────────────────────────────────────────

# API Metrics
API_REQUEST_COUNT = Counter(
    "logistics_api_requests_total",
    "Total number of API requests",
    ["method", "endpoint", "status_code"],
)

API_REQUEST_DURATION = Histogram(
    "logistics_api_request_duration_seconds",
    "API request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Database Metrics
DB_OPERATION_COUNT = Counter(
    "logistics_db_operations_total",
    "Total number of database operations",
    ["operation", "table", "status"],
)

DB_OPERATION_DURATION = Histogram(
    "logistics_db_operation_duration_seconds",
    "Database operation duration in seconds",
    ["operation", "table"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

# Business Metrics
ORDERS_PROCESSED = Counter(
    "logistics_orders_processed_total", "Total number of orders processed", ["status"]
)

ROUTES_PLANNED = Counter(
    "logistics_routes_planned_total", "Total number of routes planned"
)

VEHICLE_UTILIZATION = Gauge(
    "logistics_vehicle_utilization_percent",
    "Vehicle utilization percentage",
    ["vehicle_id", "vehicle_name"],
)

# External API Metrics
EXTERNAL_API_CALLS = Counter(
    "logistics_external_api_calls_total",
    "Total number of external API calls",
    ["api_name", "status"],
)

EXTERNAL_API_DURATION = Histogram(
    "logistics_external_api_duration_seconds",
    "External API call duration in seconds",
    ["api_name"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)


# ─── Middleware ────────────────────────────────────────────────────


async def metrics_middleware(request: Request, call_next):
    """Middleware สำหรับเก็บ API metrics"""
    start_time = time.time()

    response = await call_next(request)

    duration = time.time() - start_time
    method = request.method
    path = request.url.path
    status_code = response.status_code

    # บันทึก metrics (normalize path to avoid high cardinality)
    normalized_path = _normalize_path(path)
    API_REQUEST_COUNT.labels(
        method=method, endpoint=normalized_path, status_code=status_code
    ).inc()
    API_REQUEST_DURATION.labels(method=method, endpoint=normalized_path).observe(
        duration
    )

    return response


# ─── Helper Functions ──────────────────────────────────────────────


def record_db_operation(operation: str, table: str, duration: float, success: bool):
    """บันทึก database operation metrics"""
    status = "success" if success else "error"
    DB_OPERATION_COUNT.labels(operation=operation, table=table, status=status).inc()
    DB_OPERATION_DURATION.labels(operation=operation, table=table).observe(duration)


def record_order_processed(status: str):
    """บันทึก order processing metrics"""
    ORDERS_PROCESSED.labels(status=status).inc()


def record_route_planned():
    """บันทึก route planning metrics"""
    ROUTES_PLANNED.inc()


def update_vehicle_utilization(vehicle_id: str, vehicle_name: str, utilization: float):
    """อัปเดต vehicle utilization metrics"""
    VEHICLE_UTILIZATION.labels(vehicle_id=vehicle_id, vehicle_name=vehicle_name).set(
        utilization
    )


def record_external_api_call(api_name: str, duration: float, success: bool):
    """บันทึก external API call metrics"""
    status = "success" if success else "error"
    EXTERNAL_API_CALLS.labels(api_name=api_name, status=status).inc()
    EXTERNAL_API_DURATION.labels(api_name=api_name).observe(duration)


# ─── Metrics Endpoint ─────────────────────────────────────────────


async def metrics_endpoint():
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
