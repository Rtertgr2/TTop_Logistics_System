import logging
import requests
from config import LINE_CHANNEL_ACCESS_TOKEN, LINE_DEFAULT_USER_ID

logger = logging.getLogger(__name__)

LINE_API_URL = "https://api.line.me/v2/bot/message/push"


def send_route_notification(routes: list[dict], user_id: str = None) -> dict:
    """ส่ง notification สรุปแผนเส้นทางไปยัง LINE"""
    if not LINE_CHANNEL_ACCESS_TOKEN:
        logger.warning("LINE_CHANNEL_ACCESS_TOKEN ไม่ได้ตั้งค่า — ข้ามการส่ง LINE notification")
        return {"status": "skipped", "message": "LINE ยังไม่ได้ตั้งค่า (ตรวจสอบ LINE_CHANNEL_ACCESS_TOKEN ใน .env)"}

    target_user_id = user_id or LINE_DEFAULT_USER_ID
    if not target_user_id:
        logger.warning("LINE_USER_ID ไม่ได้ตั้งค่า — ข้ามการส่ง LINE notification")
        return {"status": "skipped", "message": "LINE_USER_ID ไม่ได้ตั้งค่า"}

    message = _build_route_message(routes)

    # LINE Messaging API มีขีดจำกัด 5000 ตัวอักษรต่อข้อความ
    _LINE_MAX_CHARS = 4900  # เผื่อ margin
    if len(message) > _LINE_MAX_CHARS:
        message = message[:_LINE_MAX_CHARS] + "\n\n... (ข้อความถูกตัด — ดูรายละเอียดเพิ่มเติมในระบบ)"

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
        }
        payload = {
            "to": target_user_id,
            "messages": [
                {
                    "type": "text",
                    "text": message
                }
            ]
        }

        response = requests.post(LINE_API_URL, json=payload, headers=headers, timeout=10)

        if response.status_code == 200:
            logger.info(f"ส่ง LINE notification สำเร็จไปยัง {target_user_id[:4]}****")
            return {"status": "sent", "message": "ส่ง LINE notification สำเร็จ"}
        else:
            error_msg = response.text
            logger.error(f"ส่ง LINE notification ไม่สำเร็จ: {response.status_code} - {error_msg}")
            return {"status": "error", "message": f"ไม่สามารถส่ง LINE notification: {error_msg}"}

    except Exception as e:
        logger.error(f"LINE notification error: {e}")
        return {"status": "error", "message": "ไม่สามารถส่ง LINE notification"}


def _build_route_message(routes: list[dict]) -> str:
    """สร้างข้อความสรุปแผนเส้นทางสำหรับส่งผ่าน LINE"""
    if not routes:
        return "ไม่มีข้อมูลเส้นทางจัดส่ง"

    message = "📦 แผนการจัดส่งสินค้าประจำวัน\n"
    message += "=" * 30 + "\n\n"

    for idx, route in enumerate(routes, 1):
        plate = route.get("plate", "")
        driver = route.get("driver", "")
        stops = route.get("stops", [])
        total_weight = route.get("total_weight", 0)
        capacity = route.get("capacity", 0)
        maps_link = route.get("google_maps_link", "")

        message += f"🚚 รถคันที่ {idx}"
        if plate:
            message += f" ({plate})"
        if driver:
            message += f" — คนขับ: {driver}"
        message += f"\n"
        message += f"   น้ำหนัก: {total_weight}/{capacity} kg\n"
        message += f"   จำนวนจุดส่ง: {len(stops)} จุด\n"

        if stops:
            message += "   จุดส่ง:\n"
            for i, stop in enumerate(stops[:5], 1):  # แสดงแค่ 5 จุดแรก
                customer = stop.get("customer", "")
                address = stop.get("address", "")
                weight = stop.get("weight", 0)
                message += f"   {i}. {customer} — {weight} kg\n"
            if len(stops) > 5:
                message += f"   ... และอีก {len(stops) - 5} จุด\n"

        if maps_link:
            message += f"\n   📍 Google Maps: {maps_link}\n"

        message += "\n"

    return message


def send_driver_notification(route: dict, driver_line_user_id: str) -> dict:
    """ส่ง notification เฉพาะรถคันเดียวไปยังคนขับ"""
    if not LINE_CHANNEL_ACCESS_TOKEN:
        return {"status": "skipped", "message": "LINE ไม่ได้ตั้งค่า"}

    if not driver_line_user_id:
        return {"status": "skipped", "message": "ไม่มี LINE User ID ของคนขับ"}

    message = _build_single_route_message(route)

    _LINE_MAX_CHARS = 4900
    if len(message) > _LINE_MAX_CHARS:
        message = message[:_LINE_MAX_CHARS] + "\n\n... (ข้อความถูกตัด)"

    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
        }
        payload = {
            "to": driver_line_user_id,
            "messages": [
                {
                    "type": "text",
                    "text": message
                }
            ]
        }

        response = requests.post(LINE_API_URL, json=payload, headers=headers, timeout=10)

        if response.status_code == 200:
            logger.info(f"ส่ง LINE notification ไปยังคนขับสำเร็จ: {driver_line_user_id[:4]}****")
            return {"status": "sent", "message": "ส่ง notification สำเร็จ"}
        else:
            error_msg = response.text
            logger.error(f"ส่ง LINE notification ไปยังคนขับไม่สำเร็จ: {response.status_code} - {error_msg}")
            return {"status": "error", "message": f"ไม่สามารถส่ง notification: {error_msg}"}

    except Exception as e:
        logger.error(f"LINE notification error: {e}")
        return {"status": "error", "message": "ไม่สามารถส่ง LINE notification"}


def _build_single_route_message(route: dict) -> str:
    """สร้างข้อความสำหรับรถคันเดียว"""
    plate = route.get("plate", "")
    driver = route.get("driver", "")
    stops = route.get("stops", [])
    total_weight = route.get("total_weight", 0)
    capacity = route.get("capacity", 0)
    maps_link = route.get("google_maps_link", "")

    message = f"📋 ใบสั่งงานจัดส่งสินค้า\n"
    message += "=" * 20 + "\n\n"

    if plate:
        message += f"🚗 ทะเบียนรถ: {plate}\n"
    if driver:
        message += f"👤 คนขับ: {driver}\n"
    message += f"📦 น้ำหนัก: {total_weight}/{capacity} kg\n"
    message += f"📍 จำนวนจุดส่ง: {len(stops)} จุด\n\n"

    if stops:
        message += "รายการจุดส่ง:\n"
        for i, stop in enumerate(stops, 1):
            customer = stop.get("customer", "")
            address = stop.get("address", "")
            weight = stop.get("weight", 0)
            eta = stop.get("eta", "")
            message += f"{i}. {customer}\n"
            message += f"   ที่อยู่: {address}\n"
            message += f"   น้ำหนัก: {weight} kg"
            if eta:
                message += f" | ETA: {eta}"
            message += "\n"

    if maps_link:
        message += f"\n🗺️ Google Maps: {maps_link}\n"

    return message
