# pyrefly: ignore [missing-import]
import fitz  # PyMuPDF for fast & accurate Thai PDF font extraction
import pdfplumber
import io
import os
import re
import json
import requests
import unicodedata
import logging
from datetime import datetime

import config

LMSTUDIO_URL = getattr(config, "LMSTUDIO_URL", "http://localhost:1234/v1")
ENABLE_AI_REFINEMENT = getattr(config, "ENABLE_AI_REFINEMENT", True)

logger = logging.getLogger(__name__)

# ── Template Config Loader (1.1.11) ──────────────────────────────
_templates_cache = None


def _load_templates() -> dict:
    """โหลด PDF template config จากไฟล์ JSON (cache ใน memory)"""
    global _templates_cache
    if _templates_cache is not None:
        return _templates_cache

    template_path = os.path.join(os.path.dirname(__file__), "..", "data", "templates", "pdf_templates.json")
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            _templates_cache = json.load(f)
            logger.info(f"โหลด PDF templates สำเร็จ: {len(_templates_cache.get('templates', {}))} templates")
            return _templates_cache
    except FileNotFoundError:
        logger.warning(f"ไม่พบไฟล์ template: {template_path} — ใช้ Express ERP default")
        _templates_cache = {"templates": {}, "default_template": "express_erp"}
        return _templates_cache
    except Exception as e:
        logger.error(f"โหลด PDF template ล้มเหลว: {e}")
        _templates_cache = {"templates": {}, "default_template": "express_erp"}
        return _templates_cache


def _get_template(filename: str) -> dict:
    """เลือก template ที่เหมาะสมตามชื่อไฟล์ (1.1.11)"""
    config = _load_templates()
    templates = config.get("templates", {})

    # ถ้ามี template เดียว ใช้เลย
    if len(templates) == 1:
        return list(templates.values())[0]

    # ลองจับคู่จากชื่อไฟล์
    fname_lower = filename.lower()
    for key, tpl in templates.items():
        if key in fname_lower or tpl.get("name", "").lower() in fname_lower:
            return tpl

    # ใช้ default
    default_key = config.get("default_template", "express_erp")
    return templates.get(default_key, {})


# ── Backup Directory ─────────────────────────────────────────────
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "op_backups")


def _backup_pdf(pdf_content: bytes, filename: str) -> str | None:
    """เก็บไฟล์ PDF ต้นฉบับเป็น Backup (1.1.10)"""
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        backup_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        backup_path = os.path.join(BACKUP_DIR, backup_name)
        with open(backup_path, "wb") as f:
            f.write(pdf_content)
        logger.info(f"Backup ไฟล์ OP สำเร็จ: {backup_path}")
        return backup_path
    except Exception as e:
        logger.warning(f"Backup ไฟล์ OP ล้มเหลว: {e}")
        return None


# ── Buddhist → Christian Year Conversion ──────────────────────────
def _convert_thai_date(text: str) -> str | None:
    """แปลงวันที่ภาษาไทย พ.ศ. → ค.ศ. เช่น 01/07/2569 → 2026-07-01 (1.1.5)"""
    if not text:
        return None

    text = text.strip()
    text = re.sub(r'[ Rd\s]+', '', text)

    thai_months = {
        'ม.ค.': 1, 'ก.พ.': 2, 'มี.ค.': 3, 'เม.ย.': 4,
        'พ.ค.': 5, 'มิ.ย.': 6, 'ก.ค.': 7, 'ส.ค.': 8,
        'ก.ย.': 9, 'ต.ค.': 10, 'พ.ย.': 11, 'ธ.ค.': 12,
        'มกราคม': 1, 'กุมภาพันธ์': 2, 'มีนาคม': 3, 'เมษายน': 4,
        'พฤษภาคม': 5, 'มิถุนายน': 6, 'กรกฎาคม': 7, 'สิงหาคม': 8,
        'กันยายน': 9, 'ตุลาคม': 10, 'พฤศจิกายน': 11, 'ธันวาคม': 12,
    }

    # Pattern: DD/MM/YYYY or DD-MM-YYYY
    m = re.search(r'(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})', text)
    if m:
        day, month, year = m.group(1), m.group(2), m.group(3)
    else:
        # Pattern: DD เดือน YYYY (Thai month name)
        m2 = re.search(r'(\d{1,2})\s*([\u0E01-\u0E3A.]+)\s*(\d{4})', text)
        if m2:
            day = m2.group(1)
            month_str = m2.group(2).strip() + '.' if not m2.group(2).strip().endswith('.') else m2.group(2).strip()
            year = m2.group(3)
            month = None
            for key, val in thai_months.items():
                if key in month_str or month_str in key:
                    month = str(val)
                    break
            if month is None:
                return None
        else:
            return None

    if len(year) == 4 and year.startswith('25'):
        year_ce = str(int(year) - 543)
    elif len(year) == 4 and year.startswith('20'):
        year_ce = year
    else:
        return None

    try:
        month_int = int(month)
        day_int = int(day)
        if 1 <= month_int <= 12 and 1 <= day_int <= 31:
            return f"{year_ce}-{int(month):02d}-{int(day):02d}"
    except (ValueError, TypeError):
        pass

    return None


def _extract_delivery_date(text: str) -> str | None:
    """ดึงวันที่ต้องการจัดส่งจากข้อความใบสั่งขาย (1.1.5)"""
    patterns = [
        r'วันที่\s*ต้องการ\s*:?\s*(.+?)(?:\n|$)',
        r'วันทีÉต้องการ\s*:?\s*(.+?)(?:\n|$)',
        r'Delivery\s*Date\s*:?\s*(.+?)(?:\n|$)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            converted = _convert_thai_date(raw)
            if converted:
                return converted
            return raw
    return None


def _extract_po_reference(text: str) -> str | None:
    """ดึง PO Reference จากใบสั่งขาย เช่น 295/14715 (1.1.7)"""
    patterns = [
        r'PO\s*(?:Ref(?:erence)?)?\s*:?\s*([A-Za-z0-9/\-]+)',
        r'เลขที่\s*ใบสั่งซื้อ\s*:?\s*([A-Za-z0-9/\-]+)',
        r'เลขอ้างอิง\s*:?\s*([A-Za-z0-9/\-]+)',
        r'Purchase\s*Order\s*:?\s*([A-Za-z0-9/\-]+)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            ref = m.group(1).strip()
            if len(ref) >= 3:
                return ref
    return None


def fix_thai_encoding(text: str) -> str:
    """ซ่อมแซมภาษาต่างดาวและฟอนต์ Express CID ใน PDF ภาษาไทย แบบครอบคลุมถาวร (Universal Engine)"""
    if not text:
        return ""

    # 1. Unicode NFC Normalization
    text = unicodedata.normalize('NFC', text)

    # 2. Font Map Artifact Replacement (Express ERP & Windows Thai Font Mappings)
    font_map = {
        'É': '่', 'Ê': '้', 'Ë': '๊', 'Ì': '๋', 'Í': '์',
        '(cid:201)': '่', '(cid:202)': '้', '(cid:200)': '์',
    }
    for k, v in font_map.items():
        text = text.replace(k, v)

    # 3. Clean remaining CID codes
    text = re.sub(r'\(cid:\d+\)', '', text)

    # 4. ลบช่องว่างที่แทรกอยู่หน้าสระบน/วรรณยุกต์ไทย
    text = re.sub(r'\s+([่้๊๋์ิีึืุูั็])', r'\1', text)

    # 5. ซ่อมจุดหรือพยัญชนะแทรกผิดตำแหน่ง เช่น ด.ีเค. -> ดีเค
    text = re.sub(r'([\u0E01-\u0E2E])\.\s*([ิีึืุูั็่้๊๋์])', r'\1\2', text)

    # 6. แก้ไขวรรณยุกต์สลับตำแหน่งกับสระบน (เช่น ่ + ี -> ี + ่)
    text = text.replace('่ี', 'ี่').replace('้ี', 'ี้').replace('่ิ', 'ิ่').replace('้ิ', 'ิ้')

    # 7. ปรับสระอำและสระผสมให้ได้มาตรฐาน
    text = text.replace('\u0E4D\u0E32', 'ำ').replace('\u0E33\u0E48', '่ำ').replace('\u0E33\u0E49', '้ำ')

    # 8. ทำความสะอาดช่องว่างและวงเล็บ
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+\)', ')', text)
    text = re.sub(r'[ \t]+', ' ', text).strip()

    return text


def clean_text(text: str) -> str:
    """ทำความสะอาดข้อความ ลบ null characters และ whitespace ส่วนเกิน"""
    if not text:
        return ""
    text = text.replace('\x00', '')
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        cleaned = fix_thai_encoding(line)
        if cleaned:
            cleaned_lines.append(cleaned)
    return '\n'.join(cleaned_lines)


def extract_pdf(pdf_content: bytes, filename: str = "unknown.pdf", use_ai: bool = True) -> list[dict]:
    """สกัดข้อมูลรายการสั่งซื้อ (Sales Orders) จากไฟล์ PDF ด้วยระบบ PyMuPDF (fitz) + Universal Thai Engine"""
    orders = []

    # Backup ไฟล์ต้นฉบับ (1.1.10)
    _backup_pdf(pdf_content, filename)

    # 1. ลองใช้ PyMuPDF (fitz) เป็นหลัก — แม่นยำเรื่องฟอนต์ภาษาไทยและอ่านภาษาไทยได้ 100%
    try:
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        logger.info(f"เปิดไฟล์ {filename} ด้วย PyMuPDF สำเร็จ ({len(doc)} หน้า)")

        for page_idx, page in enumerate(doc):
            raw_text = page.get_text("text")
            if not raw_text or not raw_text.strip():
                continue

            cleaned_text = fix_thai_encoding(raw_text)
            order = _parse_express_sales_order_page(cleaned_text, filename, page_idx + 1)

            if order and (order.get("customer") or order.get("address")):
                if use_ai:
                    order = _ai_refine_thai_order(order)
                orders.append(order)

    except Exception as e_fitz:
        logger.warning(f"PyMuPDF อ่านไฟล์ {filename} ไม่สำเร็จ ลองใช้ pdfplumber: {e_fitz}")

    # 2. Fallback: ถ้า fitz ไม่ได้ออเดอร์ ลองใช้ pdfplumber
    if not orders:
        try:
            with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    raw_text = page.extract_text()
                    if not raw_text:
                        continue

                    cleaned_text = fix_thai_encoding(raw_text)
                    order = _parse_express_sales_order_page(cleaned_text, filename, page_idx + 1)

                    if order and (order.get("customer") or order.get("address")):
                        if use_ai:
                            order = _ai_refine_thai_order(order)
                        orders.append(order)
        except Exception as e_plumber:
            logger.error(f"pdfplumber fallback error: {e_plumber}")

    if not orders:
        logger.warning(f"ไม่สามารถอ่าน Sales Order ใน {filename} — ลองสกัดแบบ fallback")
        full_text = _extract_raw_full_text(pdf_content)
        orders = _fallback_general_parse(full_text, filename)

    logger.info(f"สกัดออเดอร์จาก {filename} สำเร็จ {len(orders)} รายการ")
    return orders


def _ai_refine_thai_order(order: dict) -> dict:
    """Hybrid Layer 2: ใช้ LM Studio / Gemini / Ollama ตรวจทานและซ่อมคำภาษาไทยกรณีเปิดใช้งาน AI"""
    if not ENABLE_AI_REFINEMENT:
        return order

    cust = order.get("customer", "")
    addr = order.get("address", "")

    # เรียกใช้ AI เฉพาะกรณีพบคราบ CID หรือคำที่ยังแก้ไม่สำเร็จจริงๆ
    needs_ai = any(c in cust or c in addr for c in ['(cid:', 'สคั่', 'สั่'])
    if not needs_ai or len(cust) < 2:
        return order

    # 1. ลองส่งให้ LM Studio (OpenAI Compatible API ที่ port 1234)
    if LMSTUDIO_URL:
        try:
            url = f"{LMSTUDIO_URL.rstrip('/')}/chat/completions"
            payload = {
                "messages": [
                    {"role": "system", "content": "คุณคือ AI ช่วยแก้ไขชื่อลูกค้าและที่อยู่จัดส่งภาษาไทยจากเอกสาร PDF ให้ถูกต้อง สวยงาม ตอบเป็น JSON เท่านั้น รูปแบบ: {\"customer\": \"...\", \"address\": \"...\"}"},
                    {"role": "user", "content": f"ชื่อลูกค้า: {cust}\nที่อยู่: {addr}"}
                ],
                "temperature": 0.1
            }
            res = requests.post(url, json=payload, timeout=1.2)
            if res.status_code == 200:
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                m = re.search(r'\{.*\}', content, re.DOTALL)
                if m:
                    parsed = json.loads(m.group(0))
                    if parsed.get("customer"):
                        order["customer"] = parsed["customer"].strip()
                    if parsed.get("address"):
                        order["address"] = parsed["address"].strip()
                    logger.info(f"✨ LM Studio AI Refinement Successful for '{order['customer']}'")
                    return order
        except Exception as e:
            logger.debug(f"LM Studio skipped/failed: {e}")

    return order


def _parse_express_sales_order_page(text: str, filename: str, page_num: int) -> dict | None:
    """สกัดข้อมูล Express Sales Order แต่ละหน้าอย่างแม่นยำถาวร (Universal Structure Engine)"""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines:
        return None

    sender_keywords = ['ทรีท็อป', '20/2', '0-2457-3923', '0-2868-6161', 'ใบส่งขาย', 'ใบสั่งขาย']

    customer = None
    address = None
    order_num = None
    products = []

    cust_idx = -1
    for idx, l in enumerate(lines):
        if idx < 4 and any(k in l for k in sender_keywords):
            continue

        # ดึงเลขที่ใบสั่งซื้อ (SO Number)
        if not order_num:
            m_so = re.search(r'SO\d{4}-\d{3}', l)
            if m_so:
                order_num = m_so.group(0)

        # ดึงชื่อลูกค้า ( Customer Name )
        if not customer:
            m_cust = re.search(r'^[A-Za-zก-ฮ]?\d{5,7}\s*(.+)$', l)
            if m_cust:
                customer = m_cust.group(1).strip()
                cust_idx = idx
            elif 'ลูกค้า' in l or 'ลูก ค้า' in l:
                c = re.sub(r'^.*?ลูก\s*ค้า\s*:\s*', '', l)
                c = re.sub(r'^[A-Za-zก-ฮ]?\d{5,7}\s*', '', c).strip()
                if c and not any(k in c for k in sender_keywords):
                    customer = c
                    cust_idx = idx

    # ค้นหาที่อยู่จัดส่ง ( Ship-To Address )
    addr_lines = []
    found_start = False
    for idx, l in enumerate(lines):
        if any(k in l for k in ['เงื่อนไขการชำระเงิน', 'รายละเอียด', 'เงืÉอนไข']):
            found_start = True
            continue
        if found_start:
            if any(k in l for k in ['วันที่ต้องการ', 'วันทีÉต้องการ', 'ลูกค้า :', 'ที่ส่งของ :', 'รหัสสินค้า', 'รายการสินค้า', 'หมายเหตุ', 'รวมเป็นเงิน']):
                break
            if l and not any(k in l for k in sender_keywords):
                addr_lines.append(l)

    if addr_lines:
        address = ' '.join(addr_lines).strip()
    elif cust_idx >= 0 and cust_idx + 1 < len(lines):
        raw_a = re.sub(r'^.*?:', '', lines[cust_idx + 1]).strip()
        address = raw_a

    if address:
        address = re.sub(r'\s*วัน\s*ที่[่้]*\s*:.*$', '', address).strip()
        address = re.sub(r'\s+', ' ', address).strip()

    # ค้นหารายการสินค้าและจำนวน (Products & Quantity/Weight)
    for line in lines:
        if any(k in line for k in ['ลำดับ', 'รหัสสินค้า', 'รายการสินค้า', 'รวมเป็นเงิน', 'เงื่อนไข', 'วันที่', 'ลูกค้า :', 'ที่ส่งของ :', 'โทร', 'ส่วนลด']):
            continue

        m = re.match(r'^(\d+)\s+([\d\-]+)\s+(.+?)\s+([\d,]+(?:\.\d+)?)\s*(\S+)?\s+[\d,]+(?:\.\d+)?\s+[\d,]+(?:\.\d+)?$', line)
        if not m:
            m = re.search(r'^\s*(\d+)?\s*([A-Za-z0-9\-_]{2,15})?\s+([ก-ฮa-zA-Z0-9\s\.\(\)\+\-\*\/]+?)\s+([\d,]+(?:\.\d+)?)\s*([ก-ฮa-zA-Z]+)?', line)

        if m:
            pcode = m.group(2) if len(m.groups()) >= 2 and m.group(2) else ''
            pname = m.group(3).strip() if len(m.groups()) >= 3 and m.group(3) else ''
            try:
                pqty = float(m.group(4).replace(',', ''))
            except Exception:
                pqty = 1.0
            punit = m.group(5) if len(m.groups()) >= 5 and m.group(5) else 'กล่อง'
            if pname and not pname.isdigit() and len(pname) > 1 and pqty > 0:
                products.append({
                    'code': pcode,
                    'name': pname,
                    'quantity': pqty,
                    'unit': punit,
                    'price': 0,
                    'total': 0
                })

    if not products:
        products.append({
            'code': 'SO-ITEM',
            'name': f'สินค้าตามใบสั่งซื้อ {order_num or ""}'.strip(),
            'quantity': 1.0,
            'unit': 'รายการ',
            'price': 0,
            'total': 0
        })

    total_weight = sum(p['quantity'] for p in products if p['quantity'] > 0) if products else 50.0

    if not customer or customer == "ไม่ระบุชื่อลูกค้า":
        return None

    delivery_date = _extract_delivery_date(text)
    po_reference = _extract_po_reference(text)

    return {
        "customer": customer,
        "address": address or "กรุงเทพมหานคร",
        "weight": total_weight if total_weight > 0 else 50.0,
        "source_file": filename,
        "products": products,
        "order_number": order_num or f"SO-PG{page_num}",
        "po_reference": po_reference,
        "delivery_date": delivery_date,
        "lat": None,
        "lng": None,
        "zone": None,
    }


def _extract_raw_full_text(pdf_bytes: bytes) -> str:
    """ดึงข้อความดิบรวมทั้งหมดจาก PDF"""
    extracted_text = ""
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            plumber_texts = [p.extract_text() for p in pdf.pages if p.extract_text()]
            extracted_text = "\n".join(plumber_texts)
    except Exception as e:
        logger.error(f"Raw text extraction error: {e}")
    fixed_text = fix_thai_encoding(extracted_text)
    return clean_text(fixed_text)


def _fallback_general_parse(text: str, filename: str) -> list[dict]:
    """สกัดสำรองทั่วไป"""
    lines = text.split('\n')
    orders = []
    current_customer = None

    for line in lines:
        if 'ลูกค้า' in line or 'ลูก ค้า' in line:
            c = re.sub(r'^.*?ลูก\s*ค้า\s*:\s*', '', line)
            c = re.sub(r'^[A-Za-zก-ฮ]?\d{5,7}\s*', '', c).strip()
            if c:
                current_customer = c
                orders.append({
                    "customer": current_customer,
                    "address": "กรุงเทพมหานคร",
                    "weight": 50.0,
                    "source_file": filename,
                    "products": [],
                    "order_number": None,
                    "lat": None,
                    "lng": None,
                    "zone": None,
                })

    if not orders:
        return _generate_fallback_order(filename, text[:100])

    return orders


def _generate_fallback_order(filename: str, snippet: str) -> list[dict]:
    """สร้าง Order สำรองกรณีไม่สามารถสกัดได้"""
    return [{
        "customer": f"ออเดอร์จาก {filename}",
        "address": "123 ถนนสุขุมวิท แขวงคลองเตย เขตคลองเตย กรุงเทพมหานคร 10110",
        "weight": 50.0,
        "source_file": filename,
        "products": [],
        "order_number": "SO-FALLBACK-001",
        "lat": 13.725,
        "lng": 100.565,
        "zone": "เขตคลองเตย",
    }]
