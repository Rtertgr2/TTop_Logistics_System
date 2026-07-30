import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import EMAIL_HOST, EMAIL_PORT, EMAIL_USER, EMAIL_PASSWORD

logger = logging.getLogger(__name__)


def send_route_email(routes: list[dict], recipient: str) -> dict:
    """ส่ง email สรุปแผนเส้นทาง พร้อม Google Maps Link"""
    if not EMAIL_USER or not EMAIL_PASSWORD:
        logger.warning("Email not configured — skipping")
        return {"status": "skipped", "message": "Email ยังไม่ได้ตั้งค่า (ตรวจสอบ EMAIL_USER และ EMAIL_PASSWORD ใน .env)"}

    msg = MIMEMultipart("alternative")
    msg["From"] = EMAIL_USER
    msg["To"] = recipient
    msg["Subject"] = "📦 แผนการจัดส่งสินค้าประจำวัน"

    # Plain text version
    text_body = _build_text_body(routes)

    # HTML version
    html_body = _build_html_body(routes)

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.send_message(msg)

        logger.info(f"Email sent to {recipient}")
        return {"status": "sent", "message": f"ส่ง email ไปยัง {recipient} สำเร็จ"}

    except Exception as e:
        logger.error(f"Email error: {e}")
        return {"status": "error", "message": str(e)}


def _build_text_body(routes: list[dict]) -> str:
    """สร้าง email body แบบ plain text"""
    body = "แผนการจัดส่งสินค้าประจำวัน\n"
    body += "=" * 40 + "\n\n"

    for route in routes:
        plate = route.get("plate", "")
        driver = route.get("driver", "")
        body += f"🚚 รถคันที่ {route['vehicle_id']}"
        if plate:
            body += f" ({plate})"
        if driver:
            body += f" — คนขับ: {driver}"
        body += f"\n   น้ำหนักรวม: {route['total_weight']} kg\n"

        for i, stop in enumerate(route.get("stops", []), 1):
            body += f"   {i}. {stop['customer']} — {stop['address']} ({stop['weight']} kg)\n"

        maps_link = route.get("google_maps_link", "")
        if maps_link:
            body += f"\n   📍 Google Maps: {maps_link}\n"

        body += "\n"

    return body


def _build_html_body(routes: list[dict]) -> str:
    """สร้าง email body แบบ HTML"""
    html = """
    <html>
    <body style="font-family: 'Sarabun', Arial, sans-serif; background: #f5f5f5; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <div style="background: linear-gradient(135deg, #4f46e5, #7c3aed); color: white; padding: 24px; text-align: center;">
                <h1 style="margin: 0; font-size: 22px;">📦 แผนการจัดส่งสินค้าประจำวัน</h1>
            </div>
            <div style="padding: 24px;">
    """

    colors = ["#3b82f6", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4"]

    for idx, route in enumerate(routes):
        color = colors[idx % len(colors)]
        plate = route.get("plate", "")
        driver = route.get("driver", "")

        html += f"""
            <div style="border-left: 4px solid {color}; padding: 16px; margin-bottom: 16px; background: #fafafa; border-radius: 0 8px 8px 0;">
                <h3 style="margin: 0 0 8px 0; color: {color};">
                    🚚 รถคันที่ {route['vehicle_id']}
                    {f'<span style="font-weight: normal; color: #666;"> — {plate}</span>' if plate else ''}
                </h3>
                {f'<p style="margin: 0 0 4px 0; color: #888; font-size: 14px;">คนขับ: {driver}</p>' if driver else ''}
                <p style="margin: 0 0 12px 0; color: #888; font-size: 14px;">น้ำหนักรวม: <strong>{route['total_weight']} kg</strong></p>
                <ol style="margin: 0; padding-left: 20px;">
        """

        for stop in route.get("stops", []):
            html += f"""
                    <li style="margin-bottom: 8px;">
                        <strong>{stop['customer']}</strong><br>
                        <span style="color: #666; font-size: 13px;">{stop['address']} — {stop['weight']} kg</span>
                    </li>
            """

        html += "</ol>"

        maps_link = route.get("google_maps_link", "")
        if maps_link:
            html += f"""
                <a href="{maps_link}" target="_blank"
                   style="display: inline-block; margin-top: 12px; padding: 8px 16px; background: {color}; color: white; text-decoration: none; border-radius: 6px; font-size: 14px;">
                    📍 เปิด Google Maps
                </a>
            """

        html += "</div>"

    html += """
            </div>
        </div>
    </body>
    </html>
    """
    return html
