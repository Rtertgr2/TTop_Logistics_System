import hashlib
import hmac
import base64
import logging
import json
from fastapi import APIRouter, Request, HTTPException
from config import LINE_CHANNEL_SECRET
from database.db import get_db
from database.models import Vehicle

logger = logging.getLogger(__name__)
router = APIRouter()


def verify_line_signature(body: bytes, signature: str) -> bool:
    """Verify X-Line-Signature using HMAC-SHA256"""
    if not LINE_CHANNEL_SECRET:
        logger.warning("LINE_CHANNEL_SECRET ไม่ได้ตั้งค่า — ปฏิเสธ (misconfiguration)")
        return False

    if not signature:
        logger.warning("Missing X-Line-Signature header")
        return False

    hash = hmac.new(
        LINE_CHANNEL_SECRET.encode("utf-8"),
        body,
        hashlib.sha256
    ).digest()
    expected = base64.b64encode(hash).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def _handle_follow_event(event: dict):
    """จัดการ follow event — คนขับ add OA เป็นเพื่อน"""
    user_id = event.get("source", {}).get("userId")
    if not user_id:
        return

    logger.info(f"New follower: {user_id}")

    db = next(get_db())
    try:
        vehicles = db.query(Vehicle).filter(
            Vehicle.line_user_id == "",
            Vehicle.active == True
        ).all()

        if vehicles:
            logger.info(f"Found {len(vehicles)} vehicles without LINE ID — awaiting manual assignment")
        else:
            logger.info("All active vehicles already have LINE ID assigned")
    except Exception as e:
        logger.error(f"Error handling follow event: {e}", exc_info=True)
    finally:
        db.close()


def _handle_message_event(event: dict):
    """จัดการ message event — ข้อความจากคนขับ"""
    user_id = event.get("source", {}).get("userId")
    message = event.get("message", {})
    text = message.get("text", "")

    if not user_id:
        return

    logger.info(f"Message from {user_id}: {text[:50]}...")


def _handle_postback_event(event: dict):
    """จัดการ postback event — การกดปุ่ม"""
    user_id = event.get("source", {}).get("userId")
    postback = event.get("postback", {})
    data = postback.get("data", "")

    if not user_id:
        return

    logger.info(f"Postback from {user_id}: {data}")


@router.post("/line/webhook")
async def line_webhook(request: Request):
    """LINE Webhook endpoint — รับ event จาก LINE Messaging API"""
    body = await request.body()
    signature = request.headers.get("X-Line-Signature", "")

    # Verify signature — reject if secret is unset or signature is invalid
    if not LINE_CHANNEL_SECRET:
        logger.error("LINE_CHANNEL_SECRET ไม่ได้ตั้งค่า — reject webhook (misconfiguration)")
        raise HTTPException(status_code=503, detail="LINE webhook not configured")

    if not signature:
        logger.warning("Missing X-Line-Signature header")
        raise HTTPException(status_code=403, detail="Missing signature")

    if not verify_line_signature(body, signature):
        logger.warning("LINE signature mismatch — ตรวจสอบ LINE_CHANNEL_SECRET ให้ตรงกับ console")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    events = payload.get("events", [])

    for event in events:
        event_type = event.get("type")

        try:
            if event_type == "follow":
                _handle_follow_event(event)
            elif event_type == "message":
                _handle_message_event(event)
            elif event_type == "postback":
                _handle_postback_event(event)
            else:
                logger.debug(f"Unhandled event type: {event_type}")
        except Exception as e:
            logger.error(f"Error processing event {event_type}: {e}", exc_info=True)

    return {"status": "ok"}
