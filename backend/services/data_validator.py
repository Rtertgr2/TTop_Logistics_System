import logging

logger = logging.getLogger(__name__)


def validate_orders(orders: list[dict]) -> list[dict]:
    """ตรวจสอบและทำความสะอาดข้อมูล orders"""
    validated = []
    for i, order in enumerate(orders):
        # ตรวจสอบว่ามี address
        if not order.get("address") or order["address"] == "ไม่ระบุที่อยู่":
            logger.warning(f"Order #{i+1} ({order.get('customer', 'unknown')}): ไม่มีที่อยู่ — ข้าม")
            continue

        # ตรวจสอบว่ามี customer
        if not order.get("customer") or order["customer"] == "ไม่ระบุชื่อลูกค้า":
            logger.warning(f"Order #{i+1}: ไม่มีชื่อลูกค้า — ใช้ 'ลูกค้า #{i+1}'")
            order["customer"] = f"ลูกค้า #{i+1}"

        # ตรวจสอบน้ำหนัก
        if order.get("weight", 0) <= 0:
            logger.warning(f"Order #{i+1} ({order['customer']}): น้ำหนัก <= 0 — ใช้ค่าเริ่มต้น 1.0")
            order["weight"] = 1.0

        # ตรวจสอบ lat/lng (ถ้ามี)
        lat = order.get("lat")
        lng = order.get("lng")
        if lat is not None and lng is not None:
            if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
                logger.warning(f"Order #{i+1} ({order['customer']}): พิกัดไม่ถูกต้อง lat={lat}, lng={lng}")
                order["lat"] = None
                order["lng"] = None

        validated.append(order)

    logger.info(f"Validated {len(validated)}/{len(orders)} orders")
    return validated
