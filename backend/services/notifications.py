"""
Notification Service — Redis-backed with in-memory fallback.
Handles alerts for failed deliveries, idle vehicles, route deviations.
"""

import json
import logging
import threading
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

# Thread-safety lock for in-memory notification store
_notif_lock = threading.Lock()


# ─── Notification Types ──────────────────────────────────────────

NOTIFICATION_TYPES = {
    "DELIVERY_FAILED": {"priority": "high", "icon": "❌", "color": "#ef4444"},
    "DELIVERY_DELAYED": {"priority": "medium", "icon": "⏰", "color": "#f59e0b"},
    "VEHICLE_IDLE": {"priority": "medium", "icon": "🚛", "color": "#3b82f6"},
    "VEHICLE_OVERFLOW": {"priority": "high", "icon": "⚠️", "color": "#ef4444"},
    "ROUTE_DEVIATION": {"priority": "high", "icon": "📍", "color": "#f59e0b"},
    "TRANSFER_SUGGESTED": {"priority": "medium", "icon": "⚖️", "color": "#8b5cf6"},
    "TRANSFER_EXECUTED": {"priority": "low", "icon": "✅", "color": "#10b981"},
    "STOP_RESCHEDULED": {"priority": "medium", "icon": "🔄", "color": "#06b6d4"},
    "SYSTEM_ALERT": {"priority": "high", "icon": "🔔", "color": "#ef4444"},
}


# ─── Redis Key Prefix ───────────────────────────────────────────
_NOTIF_KEY = "notifications:list"
_NOTIF_COUNT_KEY = "notifications:counter"
_NOTIF_MAX = 200


def _get_redis():
    """Try to get Redis client from cache module."""
    try:
        from services.cache import get_redis_client

        return get_redis_client()
    except Exception:
        return None


def _is_redis_available() -> bool:
    return _get_redis() is not None


# ─── Notification Store (Redis or In-Memory) ────────────────────

# In-memory fallback
_notifications: list[dict] = []
_notification_counter = 0


def _load_notifications_from_redis() -> list[dict]:
    """Load notifications list from Redis."""
    client = _get_redis()
    if client is None:
        return _notifications
    try:
        data = client.get(_NOTIF_KEY)
        if data:
            return json.loads(data)
        return []
    except Exception as e:
        logger.warning(f"Redis load notifications error: {e}")
        return _notifications


def _save_notifications_to_redis(notifs: list[dict]):
    """Save notifications list to Redis."""
    client = _get_redis()
    if client is None:
        return
    try:
        client.set(_NOTIF_KEY, json.dumps(notifs, ensure_ascii=False))
    except Exception as e:
        logger.warning(f"Redis save notifications error: {e}")


def _get_next_id() -> int:
    """Get next notification ID (Redis auto-increment or in-memory counter)."""
    global _notification_counter
    client = _get_redis()
    if client is not None:
        try:
            return int(client.incr(_NOTIF_COUNT_KEY))
        except Exception:
            logger.warning("Failed to increment notification counter")
    with _notif_lock:
        _notification_counter += 1
        return _notification_counter


def add_notification(
    notif_type: str,
    title: str,
    message: str,
    route_id: int | None = None,
    vehicle_id: int | None = None,
    stop_id: int | None = None,
    target_role: str = "dispatcher",
) -> dict:
    """เพิ่ม notification ใหม่"""
    notif_id = _get_next_id()
    type_info = NOTIFICATION_TYPES.get(
        notif_type, {"priority": "medium", "icon": "🔔", "color": "#6b7280"}
    )

    notification = {
        "id": notif_id,
        "type": notif_type,
        "priority": type_info["priority"],
        "icon": type_info["icon"],
        "color": type_info["color"],
        "title": title,
        "message": message,
        "route_id": route_id,
        "vehicle_id": vehicle_id,
        "stop_id": stop_id,
        "target_role": target_role,
        "read": False,
        "created_at": datetime.now(UTC).isoformat(),
    }

    if _is_redis_available():
        notifs = _load_notifications_from_redis()
        notifs.insert(0, notification)
        if len(notifs) > _NOTIF_MAX:
            notifs = notifs[:_NOTIF_MAX]
        _save_notifications_to_redis(notifs)
    else:
        with _notif_lock:
            _notifications.insert(0, notification)
            if len(_notifications) > _NOTIF_MAX:
                _notifications.pop()

    logger.info(f"Notification [{notif_type}]: {title}")
    return notification


def get_notifications(
    target_role: str | None = None, unread_only: bool = False, limit: int = 50
) -> list[dict]:
    """ดึง notifications"""
    if _is_redis_available():
        result = _load_notifications_from_redis()
    else:
        with _notif_lock:
            result = list(_notifications)

    if target_role:
        result = [n for n in result if n["target_role"] in (target_role, "all")]

    if unread_only:
        result = [n for n in result if not n["read"]]

    return result[:limit]


def mark_notification_read(
    notification_id: int, target_role: str | None = None
) -> bool:
    """ทำเครื่องหมาย notification เป็นอ่านแล้ว (ตรวจสอบสิทธิ์ตาม role)"""
    if _is_redis_available():
        notifs = _load_notifications_from_redis()
        for n in notifs:
            if n["id"] == notification_id:
                if target_role and n["target_role"] not in (target_role, "all"):
                    return False
                n["read"] = True
                _save_notifications_to_redis(notifs)
                return True
        return False
    else:
        for n in _notifications:
            if n["id"] == notification_id:
                if target_role and n["target_role"] not in (target_role, "all"):
                    return False
                n["read"] = True
                return True
        return False


def mark_all_read(target_role: str | None = None) -> int:
    """ทำเครื่องหมายทั้งหมดเป็นอ่านแล้ว"""
    if _is_redis_available():
        notifs = _load_notifications_from_redis()
        count = 0
        for n in notifs:
            if target_role and n["target_role"] not in (target_role, "all"):
                continue
            if not n["read"]:
                n["read"] = True
                count += 1
        _save_notifications_to_redis(notifs)
        return count
    else:
        count = 0
        for n in _notifications:
            if target_role and n["target_role"] not in (target_role, "all"):
                continue
            if not n["read"]:
                n["read"] = True
                count += 1
        return count


def get_unread_count(target_role: str | None = None) -> int:
    """นับจำนวน unread notifications"""
    if _is_redis_available():
        notifs = _load_notifications_from_redis()
    else:
        notifs = _notifications

    count = 0
    for n in notifs:
        if target_role and n["target_role"] not in (target_role, "all"):
            continue
        if not n["read"]:
            count += 1
    return count


# ─── Auto-Generate Notifications ─────────────────────────────────


def notify_delivery_failed(
    customer: str,
    driver: str,
    reason: str,
    route_id: int | None = None,
    stop_id: int | None = None,
):
    """แจ้งเตือนเมื่อส่งไม่สำเร็จ"""
    add_notification(
        "DELIVERY_FAILED",
        f"ส่งไม่สำเร็จ: {customer}",
        f"คนขับ {driver} ไม่สามารถส่งของให้ {customer} ได้ — เหตุผล: {reason}",
        route_id=route_id,
        stop_id=stop_id,
        target_role="dispatcher",
    )


def notify_transfer_suggested(
    source_driver: str, target_driver: str, customer: str, score: float
):
    """แจ้งเตือนเมื่อมีคำแนะนำย้าย stop"""
    add_notification(
        "TRANSFER_SUGGESTED",
        f"แนะนำย้าย: {customer}",
        f"ย้ายจาก {source_driver} → {target_driver} (score: {score})",
        target_role="dispatcher",
    )


def notify_transfer_executed(
    source_driver: str, target_driver: str, customer: str, approved_by: str
):
    """แจ้งเตือนเมื่อย้าย stop สำเร็จ"""
    add_notification(
        "TRANSFER_EXECUTED",
        f"ย้ายสำเร็จ: {customer}",
        f"{source_driver} → {target_driver} โดย {approved_by}",
        target_role="all",
    )


def notify_stop_rescheduled(customer: str, reason: str, dispatcher: str):
    """แจ้งเตือนเมื่อเลื่อนจัดส่ง"""
    add_notification(
        "STOP_RESCHEDULED",
        f"เลื่อนจัดส่ง: {customer}",
        f"เหตุผล: {reason} — โดย {dispatcher}",
        target_role="all",
    )
