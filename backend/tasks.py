"""
Celery Tasks — Background jobs for VRP optimization, geocoding, etc.
Task status stored in Redis for cross-process visibility (API <-> Worker).
"""

import json
import logging
import os
import time
import uuid
from datetime import UTC, datetime

from celery import shared_task

logger = logging.getLogger(__name__)

# ── Redis task status store ──────────────────────────────────────
# Uses Redis so both FastAPI and Celery worker can read/write status

_redis_client = None
TASK_STATUS_TTL = 3600  # 1 hour


def _get_redis():
    """Lazy Redis client for task status storage."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis

            url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            _redis_client = redis.from_url(url, decode_responses=True)
            _redis_client.ping()
        except Exception as e:
            logger.warning(f"Redis not available for task status: {e}")
            _redis_client = False
    return _redis_client


def _task_key(task_id: str) -> str:
    return f"task_status:{task_id}"


def get_task_status(task_id: str) -> dict:
    """Get task status by ID from Redis."""
    r = _get_redis()
    if r:
        try:
            data = r.get(_task_key(task_id))
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Redis get task status failed: {e}")
    return {"status": "unknown", "task_id": task_id}


def _update_task(task_id: str, **kwargs):
    """Update task status in Redis."""
    r = _get_redis()
    if r:
        try:
            key = _task_key(task_id)
            existing = r.get(key)
            data = json.loads(existing) if existing else {"task_id": task_id}
            data.update(kwargs)
            r.setex(key, TASK_STATUS_TTL, json.dumps(data, default=str))
            return
        except Exception as e:
            logger.warning(f"Redis update task status failed: {e}")
    # Fallback: log warning
    logger.debug(f"Task {task_id} status update skipped (no Redis): {kwargs}")


# ── Tasks ────────────────────────────────────────────────────────


@shared_task(bind=True, name="tasks.optimize_routes_task")
def optimize_routes_task(self, orders: list, depot: dict, task_id: str | None = None):
    """
    Background VRP optimization task.
    Called asynchronously via POST /api/v1/plan-routes/async
    """
    if not task_id:
        task_id = str(uuid.uuid4())

    _update_task(task_id, status="processing", started_at=datetime.now(UTC).isoformat())
    logger.info(f"Task {task_id}: Starting VRP optimization for {len(orders)} orders")

    try:
        from database.db import save_route_plan
        from metrics import record_route_planned
        from services.geocoding import geocode_orders
        from services.route_optimizer import load_vehicles, optimize_routes

        start_time = time.time()

        _update_task(task_id, step="geocoding", progress=10)
        logger.info(f"Task {task_id}: Geocoding {len(orders)} orders")
        orders = geocode_orders(orders, force_refresh=True)

        _update_task(task_id, step="loading_vehicles", progress=20)
        vehicles = load_vehicles()

        _update_task(task_id, step="optimizing", progress=30)
        logger.info(f"Task {task_id}: Running VRP optimization")
        result = optimize_routes(orders, vehicles=vehicles, depot=depot)
        routes = result["routes"]
        warnings = result.get("warnings", [])
        clustered = result.get("clustered", False)

        _update_task(task_id, step="saving", progress=90)
        plan_id = save_route_plan(routes, depot)

        duration = time.time() - start_time
        record_route_planned()

        logger.info(
            f"Task {task_id}: VRP optimization completed in {duration:.1f}s, plan_id={plan_id}"
        )

        final_result = {
            "plan_id": plan_id,
            "routes": routes,
            "total_orders": len(orders),
            "total_vehicles": len(routes),
            "depot": depot,
            "warnings": warnings,
            "clustered": clustered,
            "task_id": task_id,
            "duration_seconds": round(duration, 2),
        }

        _update_task(
            task_id,
            status="completed",
            result=final_result,
            completed_at=datetime.now(UTC).isoformat(),
            duration_seconds=round(duration, 2),
        )

        return final_result

    except Exception as e:
        logger.exception(f"Task {task_id}: VRP optimization failed")
        # Set "retrying" before retry, not "failed"
        retries = self.request.retries
        if retries < self.max_retries:
            _update_task(
                task_id,
                status="retrying",
                error=str(e),
                retry_count=retries + 1,
                next_retry_at=datetime.now(UTC).isoformat(),
            )
            raise self.retry(exc=e, countdown=60)
        else:
            _update_task(
                task_id,
                status="failed",
                error=str(e),
                completed_at=datetime.now(UTC).isoformat(),
            )
            raise


@shared_task(bind=True, name="tasks.geocode_orders_task")
def geocode_orders_task(self, orders: list, task_id: str | None = None):
    """
    Background geocoding task for batch processing.
    """
    if not task_id:
        task_id = str(uuid.uuid4())

    _update_task(task_id, status="processing", started_at=datetime.now(UTC).isoformat())
    logger.info(f"Task {task_id}: Starting batch geocoding for {len(orders)} orders")

    try:
        from services.geocoding import geocode_orders

        start_time = time.time()
        geocoded = geocode_orders(orders, force_refresh=True)
        duration = time.time() - start_time

        result = {
            "orders": geocoded,
            "total": len(geocoded),
            "task_id": task_id,
            "duration_seconds": round(duration, 2),
        }

        _update_task(
            task_id,
            status="completed",
            result=result,
            completed_at=datetime.now(UTC).isoformat(),
        )

        return result

    except Exception as e:
        logger.exception(f"Task {task_id}: Geocoding failed")
        retries = self.request.retries
        if retries < self.max_retries:
            _update_task(
                task_id,
                status="retrying",
                error=str(e),
                retry_count=retries + 1,
            )
            raise self.retry(exc=e, countdown=30)
        else:
            _update_task(
                task_id,
                status="failed",
                error=str(e),
                completed_at=datetime.now(UTC).isoformat(),
            )
            raise
