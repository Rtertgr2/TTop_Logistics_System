import io
import logging
import os

logger = logging.getLogger(__name__)

from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


def create_test_pdf():
    # ลองหา font ที่รองรับภาษาไทย
    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansThai-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]

    font_name = "Helvetica"
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont("ThaiFont", font_path))
                font_name = "ThaiFont"
                break
            except Exception:
                logger.warning(f"Failed to register font {font_path}")
                continue

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    text = """ลูกค้า: บริษัท ABC จำกัด
ที่อยู่: 123 ถนนสุขุมวิท แขวงคลองเตย เขตคลองเตย กรุงเทพฯ 10110
น้ำหนัก: 50 kg

ลูกค้า: ห้างสรรพสินค้า XYZ
ที่อยู่: 456 ถนนรัชดาภิเษก อำเภอเมือง จังหวัดนนทบุรี 11000
น้ำหนัก: 75 kg
"""

    text_object = c.beginText(100, 700)
    text_object.setFont(font_name, 12)
    for line in text.split("\n"):
        text_object.textLine(line)
    c.drawText(text_object)
    c.save()

    return buffer.getvalue()


if __name__ == "__main__":
    from services.pdf_extractor import extract_pdf

    pdf_content = create_test_pdf()
    print(f"PDF size: {len(pdf_content)} bytes")

    orders = extract_pdf(pdf_content, "test.pdf")
    print(f"Orders found: {len(orders)}")
    for order in orders:
        print(f"  - {order}")
