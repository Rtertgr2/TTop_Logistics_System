"""
Celery Application — Background task queue for VRP optimization and other heavy jobs
Uses Redis as broker and result backend.
"""

import logging
import os
from urllib.parse import urlparse, urlunparse

from celery import Celery

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _make_redis_url(base_url: str, db: int) -> str:
    """Safely change the Redis DB number in a URL without corrupting password/port."""
    parsed = urlparse(base_url)
    # Reconstruct with only the path (DB number) changed
    return urlunparse(parsed._replace(path=f"/{db}"))


REDIS_BROKER_URL = _make_redis_url(REDIS_URL, db=1)  # DB 1 for Celery broker
REDIS_RESULT_URL = _make_redis_url(REDIS_URL, db=2)  # DB 2 for results

celery_app = Celery(
    "logistics",
    broker=REDIS_BROKER_URL,
    backend=REDIS_RESULT_URL,
    include=["tasks"],  # Explicit task discovery
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone=os.getenv("CELERY_TIMEZONE", "Asia/Bangkok"),
    enable_utc=True,
    # Task settings
    task_track_started=True,
    task_time_limit=300,  # 5 minutes hard limit
    task_soft_time_limit=240,  # 4 minutes soft limit
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time per worker (VRP is CPU-heavy)
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks to prevent memory leaks
    # Result settings
    result_expires=3600,  # Results expire after 1 hour
    # Retry settings
    task_default_retry_delay=60,
    task_max_retries=3,
    # Queue routing
    task_routes={
        "tasks.optimize_routes_task": {"queue": "vrp"},
        "tasks.geocode_orders_task": {"queue": "geocoding"},
    },
    task_default_queue="default",
)

# Mask password in broker URL for logging
_safe_broker_url = (
    REDIS_BROKER_URL.split("@")[-1] if "@" in REDIS_BROKER_URL else REDIS_BROKER_URL
)
logger.info(f"Celery app configured with broker: {_safe_broker_url}")
