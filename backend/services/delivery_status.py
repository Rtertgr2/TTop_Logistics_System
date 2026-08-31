"""
Delivery Status State Machine
Manages stop status transitions: PENDING → IN_TRANSIT → ARRIVED → DELIVERED/FAILED/PARTIAL/RESCHEDULED
"""

import logging

logger = logging.getLogger(__name__)

# Valid status transitions
VALID_TRANSITIONS = {
    "PENDING": ["IN_TRANSIT"],
    "IN_TRANSIT": ["ARRIVED"],
    "ARRIVED": ["DELIVERED", "FAILED", "PARTIAL"],
    "PARTIAL": ["DELIVERED", "FAILED"],
    "DELIVERED": [],  # Terminal state
    "FAILED": ["RESCHEDULED"],  # Can reschedule failed deliveries
    "RESCHEDULED": ["PENDING"],  # Rescheduled goes back to pending
}

# Status display names (Thai)
STATUS_LABELS = {
    "PENDING": "รอจัดส่ง",
    "IN_TRANSIT": "กำลังขนส่ง",
    "ARRIVED": "ถึงจุดส่งแล้ว",
    "DELIVERED": "ส่งสำเร็จ",
    "FAILED": "ส่งไม่สำเร็จ",
    "PARTIAL": "ส่งบางส่วน",
    "RESCHEDULED": "เลื่อนจัดส่ง",
}

# Status colors for UI
STATUS_COLORS = {
    "PENDING": "#6b7280",  # gray
    "IN_TRANSIT": "#3b82f6",  # blue
    "ARRIVED": "#f59e0b",  # amber
    "DELIVERED": "#10b981",  # green
    "FAILED": "#ef4444",  # red
    "PARTIAL": "#8b5cf6",  # purple
    "RESCHEDULED": "#06b6d4",  # cyan
}


def validate_transition(current_status: str, new_status: str) -> bool:
    """ตรวจสอบว่าการเปลี่ยนสถานะถูกต้องหรือไม่"""
    if current_status not in VALID_TRANSITIONS:
        return False
    return new_status in VALID_TRANSITIONS[current_status]


def get_valid_next_statuses(current_status: str) -> list[str]:
    """ดึงสถานะถัดไปที่สามารถเปลี่ยนได้"""
    return VALID_TRANSITIONS.get(current_status, [])


def get_status_label(status: str) -> str:
    """ดึงชื่อสถานะภาษาไทย"""
    return STATUS_LABELS.get(status, status)


def get_status_color(status: str) -> str:
    """ดึงสีของสถานะ"""
    return STATUS_COLORS.get(status, "#6b7280")


def calculate_delivery_summary(stops: list[dict]) -> dict:
    """คำนวณสรุปสถานะการจัดส่งจากรายการ stops"""
    summary = {
        "total": len(stops),
        "pending": 0,
        "in_transit": 0,
        "arrived": 0,
        "delivered": 0,
        "failed": 0,
        "partial": 0,
        "rescheduled": 0,
        "completion_pct": 0,
    }

    for stop in stops:
        status = (stop.get("delivery_status") or "PENDING").upper()
        if status == "PENDING":
            summary["pending"] += 1
        elif status == "IN_TRANSIT":
            summary["in_transit"] += 1
        elif status == "ARRIVED":
            summary["arrived"] += 1
        elif status == "DELIVERED":
            summary["delivered"] += 1
        elif status == "FAILED":
            summary["failed"] += 1
        elif status == "PARTIAL":
            summary["partial"] += 1
        elif status == "RESCHEDULED":
            summary["rescheduled"] += 1

    completed = (
        summary["delivered"]
        + summary["failed"]
        + summary["partial"]
        + summary["rescheduled"]
    )
    if summary["total"] > 0:
        summary["completion_pct"] = round((completed / summary["total"]) * 100)

    return summary
