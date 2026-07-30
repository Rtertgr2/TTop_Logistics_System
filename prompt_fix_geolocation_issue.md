# 🎯 Prompt: แก้ไขปัญหาพิกัดคลาดเคลื่อนในระบบจัดคิวและเส้นทางรถขนส่ง

---

## 1. Context / บริบทของระบบ

เรากำลังพัฒนา **Web Application ระบบจัดคิวและเส้นทางรถขนส่ง (Routing & Dispatching System)** ที่มีขั้นตอนการทำงานดังนี้:

1. **อ่านไฟล์ OP (ใบสั่งขาย / Sales Order)** → สกัดข้อมูลออเดอร์ (ชื่อลูกค้า, ที่อยู่จัดส่ง, ชื่อสินค้า, จำนวนสินค้า)
2. **Geocoding** → แปลงที่อยู่จัดส่งเป็นพิกัด lat/lng
3. **Distance Matrix** → ดึงระยะทางและเวลาเดินทางจาก Map API
4. **VRP Optimization** → คำนวณเส้นทางและจำนวนรถที่เหมาะสม (ใช้ OR-Tools หรือ engine คล้ายกัน)
5. **สร้าง Route Plan** → ตารางการเดินรถสำหรับแต่ละคัน

ปัจจุบันระบบถูกออกแบบเป็น **2 ส่วนหลัก**:
- **Data Parser** (Python Script): อ่านไฟล์ OP (PDF) → แปลงเป็น JSON
- **Routing Engine** (Python): รับ JSON → คำนวณเส้นทาง → ส่งผลลัพธ์

---

## 2. Problem Statement / ปัญหาที่พบ

**พิกัด (lat/lng) ที่ได้จากการ Geocoding มีความคลาดเคลื่อนจากสถานที่จริง**

ผลกระทบที่เกิดขึ้น:
- Distance Matrix คำนวณระยะทางและเวลาผิด → Route Plan ไม่สมจริง
- คนขับรถไปถึงแล้วไม่เจอจุดรับ/ส่งจริง → เสียเวลา, เสียค่าน้ำมัน, ลูกค้าไม่พอใจ
- VRP Optimization คำนวณตามพิกัดผิด → ลำดับการแวะผิดทั้งหมด
- ถ้านำไปใช้งานจริงจะส่งผลกระทบต่อการขนส่งและต้นทุนในระยะยาว

**สาเหตุที่คาดการณ์:**
- Geocoding จากที่อยู่ไม่แม่นยำ (ชื่อซอยซ้ำ, ย่อหน้าผิด, ชื่อหมู่บ้านคล้ายกัน)
- พิกัดเก็บทศนิยมไม่เพียงพอ (ต่ำกว่า 7-8 ตำแหน่ง)
- ไม่มีการตรวจสอบย้อนกลับ (Reverse Geocoding)
- ไม่มีการ Snap to Road ก่อนคำนวณ
- ไม่มีชั้นการยืนยันจากผู้ใช้ (User Verification)
- ไม่มีระบบ Feedback Loop จากคนขับรถ

---

## 3. Requirements / สิ่งที่ต้องการ

### 3.1 ส่วน Data Parser - อ่านไฟล์ OP (ใบสั่งขาย)

ไฟล์ OP ที่รับเข้ามาเป็น **PDF ใบสั่งขาย (Sales Order)** จากบริษัท ทรีท็อปเคมิคัลแอนด์ฟู้ดส์ คอร์ปอเรชั่น จำกัด

#### ข้อมูลที่ต้องดึงจากใบสั่งขาย (Mandatory Fields)

| ฟิลด์ | ตำแหน่งในเอกสาร | ตัวอย่างจาก SO6907-017 |
|-------|----------------|----------------------|
| **order_id** | เลขที่ใบสั่งขาย | `SO6907-017` |
| **customer_name** | ชื่อลูกค้า / ที่ส่งของ | `ย101609ยีสต์ กะ เนย (สำนักงานใหญ่)` |
| **delivery_address** | ที่อยู่จัดส่ง | `23-25 ถนนจักรวรรดิ แขวงจักรวรรดิ เขตสัมพันธวงศ์ กรุงเทพมหานคร 10100` |
| **delivery_date** | วันที่ต้องการ | `01/07/2569` |
| **items** | รายการสินค้าในตาราง | ดูตัวอย่างด้านล่าง |
| **po_reference** | หมายเหตุ/PO ลูกค้า | `295/14715` |

#### ตัวอย่างโครงสร้างรายการสินค้า (Items Table)

จากใบสั่งขาย SO6907-017:

| ลำดับ | รหัสสินค้า | รายการสินค้า | จำนวน | หน่วย |
|------|-----------|-------------|-------|------|
| 1 | 92-0101 | CAKE | 1 | กล่อง |
| 2 | 91-0201 | CREAM | 2 | กล่อง |
| 3 | 91-0202 | CREAM 1x16 | 3 | กล่อง |

#### จุดที่ Parser ต้องระวัง

- **ชื่อลูกค้ามีตัวเลขคละกับชื่อ**: เช่น `ย101609ยีสต์ กะ เนย` → ดึงทั้งสตริงมาเลย อย่าตัดตัวเลขออก
- **วันที่เป็น พ.ศ.**: `01/07/2569` → ต้องแปลงเป็น ค.ศ. `2026-07-01`
- **ที่อยู่อาจขาดคำนำหน้า**: เช่น ไม่มีคำว่า "จังหวัด" นำหน้า → ตรวจสอบรหัสไปรษณีย์ (5 หลัก) แล้วเติมคำนำหน้าที่ขาดหาย
- **สินค้าอาจมีหลายบรรทัดแต่เป็นรายการเดียวกัน**: ใช้ `product_code` เป็นตัวแบ่ง record
- **หน่วยนับอาจไม่ใช่ "กล่อง" เสมอไป**: อาจเป็น ถุง, แพ็ค, ชิ้น → ดึงคอลัมน์ `หน่วย` มาด้วย

#### JSON Output ที่ Parser ต้องส่งออก (ส่งต่อไปยัง Routing Engine)

```json
{
  "order_id": "SO6907-017",
  "customer_name": "ย101609ยีสต์ กะ เนย (สำนักงานใหญ่)",
  "delivery_address": "23-25 ถนนจักรวรรดิ แขวงจักรวรรดิ เขตสัมพันธวงศ์ กรุงเทพมหานคร 10100",
  "delivery_date": "2026-07-01",
  "po_reference": "295/14715",
  "items": [
    {
      "product_code": "92-0101",
      "product_name": "CAKE",
      "quantity": 1,
      "unit": "กล่อง",
      "weight_per_unit_kg": null
    },
    {
      "product_code": "91-0201",
      "product_name": "CREAM",
      "quantity": 2,
      "unit": "กล่อง",
      "weight_per_unit_kg": null
    },
    {
      "product_code": "91-0202",
      "product_name": "CREAM 1x16",
      "quantity": 3,
      "unit": "กล่อง",
      "weight_per_unit_kg": null
    }
  ],
  "total_quantity": 6,
  "total_boxes": 6,
  "source_file": "so6907-017.pdf",
  "parsed_at": "2026-07-28T12:04:00+07:00"
}
```

#### สิ่งที่ Parser ต้องทำเพิ่ม (เชื่อมโยงกับปัญหาพิกัด)

- [ ] หลัง parse ที่อยู่เสร็จ ต้องส่ง `delivery_address` ไปยัง Geocoding Module ทันที
- [ ] ถ้า parse ไม่ได้หรือข้อมูลไม่ครบ ให้ reject พร้อมระบุว่าฟิลด์ไหนหาย
- [ ] เก็บไฟล์ OP ต้นฉบับไว้เป็น backup อย่างน้อย 7 วัน

---

### 3.2 ส่วน Pre-Processing Validation (ก่อน Geocode)

- [ ] Validate รูปแบบที่อยู่ไทยให้ครบถ้วน (เลขที่, ถนน, แขวง/ตำบล, เขต/อำเภอ, จังหวัด, รหัสไปรษณีย์)
- [ ] ตรวจสอบว่าที่อยู่อยู่ในประเทศไทยจริง (Bounding Box: Lat 5-21N, Lon 97-106E)
- [ ] ใช้ Multi-Provider Geocoding (อย่างน้อย 2 แหล่ง: เช่น Google Maps + Nominatim/OpenStreetMap) แล้วเปรียบเทียบผลลัพธ์
- [ ] คำนวณ **Confidence Score** ให้แต่ละพิกัด (เช่น ตรงกัน 2 แหล่ง = 100%, ตรงกัน 1 แหล่ง = 50%, ห่างกัน > 500 เมตร = ต่ำ)

### 3.3 ส่วน Post-Geocoding Validation (หลัง Geocode)

- [ ] ใช้ **Reverse Geocoding** ย้อนกลับมาเป็นที่อยู่ แล้วเทียบกับที่อยู่ต้นฉบับ
- [ ] ใช้ **Snap to Road API** ดึงพิกัดให้ติดถนนที่ใกล้ที่สุดก่อนส่งเข้า Distance Matrix
- [ ] Flag จุดที่มีความน่าเชื่อถือต่ำ (Confidence Score < 70%) เพื่อให้ผู้ใช้ตรวจสอบ

### 3.4 Database Schema ปรับปรุง

- [ ] แยกเก็บพิกัดเป็น 2 ชุด:
  - raw_geocode_lat / raw_geocode_lng (พิกัดจาก Geocoding ดิบ)
  - verified_lat / verified_lng (พิกัดที่ผ่านการยืนยันแล้ว)
- [ ] เก็บ confidence_score (FLOAT, 0-100)
- [ ] เก็บ geocode_provider (STRING, เช่น "google", "nominatim")
- [ ] เก็บ is_verified (BOOLEAN)
- [ ] เก็บ verified_by (STRING, เช่น "system", "user", "driver")
- [ ] เก็บ verified_at (TIMESTAMP)
- [ ] ต้องเก็บพิกัดด้วยความละเอียดสูง: DECIMAL(10, 8) สำหรับ lat และ DECIMAL(11, 8) สำหรับ lng

### 3.5 Frontend: User Verification Flow

- [ ] สร้างหน้า/Modal **"Review & Confirm Location"** ที่แสดง:
  - Pin บนแผนที่ (Interactive Map เช่น Leaflet / Mapbox / Google Maps)
  - ที่อยู่ต้นฉบับ
  - Confidence Score
  - ภาพถ่ายดาวเทียม / Street View (ถ้าเป็นไปได้)
- [ ] ให้ผู้ใช้สามารถ **ลาก Pin** ไปวางที่ตำแหน่งจริงได้
  - เมื่อลาก Pin แล้ว ให้ Reverse Geocode อัตโนมัติเพื่อแสดงที่อยู่ใหม่
  - ให้ผู้ใช้ยืนยันว่าถูกต้อง
- [ ] ถ้า Confidence Score < 70% ให้ **บังคับ**ให้ผู้ใช้ยืนยันก่อนบันทึก order
- [ ] ถ้า Confidence Score >= 70% ให้แสดงแจ้งเตือนเบาๆ แต่ไม่บังคับ

### 3.6 Driver Feedback Loop

- [ ] สร้างฟีเจอร์ **"Report Wrong Pin"** ในแอป/หน้าเว็บสำหรับคนขับรถ
  - ให้คนขับกดปุ่ม "พิกัดผิด" พร้อมระบุพิกัดจริงที่ตนอยู่ (ใช้ GPS ของอุปกรณ์)
  - ให้คนขับถ่ายรูปประกอบ (optional)
  - ให้คนขับใส่หมายเหตุ (optional)
- [ ] เมื่อมีการ Report:
  - อัปเดต verified_lat / verified_lng ในฐานข้อมูล
  - ตั้ง verified_by = "driver"
  - เก็บประวัติการแก้ไขไว้ใน Log
  - ส่งแจ้งเตือนไปยัง Admin

### 3.7 Admin Dashboard

- [ ] สร้างหน้า **"Location Quality Report"** ที่แสดง:
  - รายการออเดอร์ที่มี Confidence Score ต่ำ
  - Heatmap ของจุดที่ถูก Report ว่าผิดบ่อย
  - สถิติความแม่นยำของแต่ละ Geocoding Provider
  - รายการที่รอการยืนยันจากผู้ใช้

---

## 4. Technical Details / รายละเอียดทางเทคนิค

### 4.1 Tech Stack ปัจจุบัน
- Backend: Python (Data Parser + Routing Engine)
- Frontend: Web Application (กรุณาระบุ framework ที่ใช้ เช่น React, Vue, Angular)
- Database: (กรุณาระบุ เช่น PostgreSQL, MySQL, MongoDB)
- Map API: (กรุณาระบุ เช่น Google Maps API, Mapbox, OpenStreetMap/Nominatim)

### 4.2 การอ่านไฟล์ OP (PDF Parser)

**เครื่องมือที่แนะนำ:**
- `pdfplumber` → ดีสุดสำหรับตารางใน PDF (ใบสั่งขายมีตารางสินค้า)
- `PyMuPDF (fitz)` → ดึงข้อความจาก PDF ได้แม่นยำ
- `camelot-py` → ถ้าตารางซับซ้อนมาก

**โครงสร้างใบสั่งขายที่ต้องรองรับ:**
- หัวกระดาษ: ชื่อบริษัท, โลโก้, เลขที่, วันที่
- ส่วนลูกค้า: ชื่อลูกค้า, ที่อยู่จัดส่ง, วันที่ต้องการ
- ตารางสินค้า: ลำดับ, รหัสสินค้า, รายการ, จำนวน, หน่วย, ราคา, จำนวนเงิน
- ส่วนท้าย: รวมเงิน, ส่วนลด, ภาษี, หมายเหตุ/PO

**ตัวอย่าง Regex Pattern สำหรับดึงข้อมูล:**
```python
# เลขที่ใบสั่งขาย
order_id_pattern = r"เลขที\s*[:\s]+(SO\d+-\d+)"

# วันที่ต้องการ (รองรับ พ.ศ.)
delivery_date_pattern = r"วันที\s*ต้องการ\s*[:\s]+(\d{2}/\d{2}/\d{4})"

# ที่อยู่จัดส่ง (หลังชื่อลูกค้า จนถึงรหัสไปรษณีย์)
address_pattern = r"ลูกค้า\s*[:\s]+.*?
(.*?)
(?:ลำดับ|รายละเอียด)"

# รหัสไปรษณีย์
postal_code_pattern = r"(\d{5})"
```

### 4.3 API ที่ต้องใช้ (ตัวอย่าง)
- **Geocoding**: Google Geocoding API / Nominatim / ฐานข้อมูลไปรษณีย์ไทย
- **Reverse Geocoding**: Google Reverse Geocoding / Nominatim Reverse
- **Snap to Road**: Google Roads API (Snap to Roads) / OSRM nearest service
- **Distance Matrix**: Google Distance Matrix API / OSRM Table service

### 4.4 การคำนวณ Confidence Score (ตัวอย่าง Algorithm)

Logic ที่แนะนำ:
1. ถ้ามีผลลัพธ์จาก provider เดียว -> 50%
2. ถ้ามี 2+ providers ให้คำนวณระยะห่างระหว่างพิกัด (Haversine distance)
   - ห่าง < 50m -> 100%
   - ห่าง 50-200m -> 80%
   - ห่าง 200-500m -> 60%
   - ห่าง > 500m -> 30%
3. ถ้า Reverse Geocoding กลับมาแล้วชื่อถนน/ตำบล ตรงกับต้นฉบับ -> +10%
4. ถ้าพิกัดอยู่นอก Bounding Box ประเทศไทย -> 0%
5. ถ้า Snap to Road แล้วห่างจากจุดเดิม > 1km -> -20%

Return: score (0-100)

### 4.5 การตรวจสอบ Bounding Box ประเทศไทย

THAILAND_BOUNDS = {
    "min_lat": 5.0,
    "max_lat": 21.0,
    "min_lng": 97.0,
    "max_lng": 106.0
}

def is_in_thailand(lat, lng):
    return (THAILAND_BOUNDS["min_lat"] <= lat <= THAILAND_BOUNDS["max_lat"] and
            THAILAND_BOUNDS["min_lng"] <= lng <= THAILAND_BOUNDS["max_lng"])

### 4.6 การ Snap to Road (ตัวอย่าง Google Roads API)

Endpoint: https://roads.googleapis.com/v1/snapToRoads
Parameters: path=lat,lng|lat,lng&key=API_KEY
ใช้ interpolated=true เพื่อให้ได้พิกัดที่ละเอียดขึ้น

---

## 5. Acceptance Criteria / เกณฑ์การยอมรับ

ระบบถือว่าสำเร็จเมื่อ:

- [ ] **AC-1**: Parser สามารถอ่านไฟล์ OP (PDF) และดึงข้อมูลครบถ้วน (ชื่อ, ที่อยู่, ชื่อสินค้า, จำนวน) ได้อย่างน้อย 95% ของไฟล์ที่ผ่าน validation
- [ ] **AC-2**: ทุกออเดอร์ที่เข้าระบบต้องมี Confidence Score ประกอบ
- [ ] **AC-3**: ออเดอร์ที่ Confidence Score < 70% ต้องถูก Flag และต้องผ่านการยืนยันจากผู้ใช้ก่อนถึงขั้นตอน VRP
- [ ] **AC-4**: พิกัดที่ใช้ใน Distance Matrix ต้องเป็นพิกัดที่ผ่านการ Snap to Road แล้ว
- [ ] **AC-5**: ผู้ใช้สามารถลาก Pin บนแผนที่เพื่อแก้ไขตำแหน่งได้
- [ ] **AC-6**: คนขับรถสามารถ Report พิกัดผิด และระบบอัปเดตพิกัดถาวรได้
- [ ] **AC-7**: Admin สามารถดูรายงาน Location Quality และ Heatmap ของปัญหาได้
- [ ] **AC-8**: ระบบต้องสามารถประมวลผลออเดอร์ได้อย่างน้อย 1,000 รายการต่อชั่วโมงโดยไม่ timeout
- [ ] **AC-9**: ต้องมี Unit Test ครอบคลุมฟังก์ชัน Parser, Validation, Confidence Score, และ Snap to Road

---

## 6. Deliverables / สิ่งที่ต้องส่งมอบ

1. **Source Code** ที่ครอบคลุม:
   - **OP Parser Module** (Python): อ่าน PDF ใบสั่งขาย → ดึงชื่อ, ที่อยู่, สินค้า, จำนวน → ส่ง JSON
   - **Validation & Confidence Score Module** (Python)
   - **API Endpoints** สำหรับ Geocoding, Reverse Geocoding, Snap to Road
   - **Frontend Component** สำหรับ Map + Pin Dragging
   - **Database Migration Script** (เพิ่มฟิลด์ใหม่)

2. **API Documentation** (Swagger/OpenAPI หรือ README)

3. **Unit Tests** (ครอบคลุมอย่างน้อย 80%)

4. **Integration Tests** (End-to-End flow จากอ่านไฟล์ OP จนถึง Route Plan)

5. **Deployment Guide** (ถ้ามีการเปลี่ยนแปลง infrastructure)

---

## 7. Constraints & Notes / ข้อจำกัดและหมายเหตุ

- ห้าม hardcode API Key ใน source code -> ใช้ Environment Variable หรือ Secret Manager
- ต้องมี Rate Limit handling สำหรับ Map API (เช่น retry with exponential backoff)
- ต้องมี Caching สำหรับ Geocoding result (เช่น Redis) เพื่อลดค่าใช้จ่าย API
- ถ้าใช้ Google Maps API ต้องระวังเรื่อง **PDPA** ในการส่งที่อยู่ลูกค้าออกไป
- ควรเก็บ Log ของทุกการ Geocode (input, output, provider, timestamp) เพื่อ Audit ย้อนหลัง
- หากใช้ Nominatim (OpenStreetMap) ต้องปฏิบัติตาม Policy (ไม่เกิน 1 request/second)
- **Parser ต้องรองรับไฟล์ OP หลายรูปแบบ**: ใบสั่งขายอาจมี template ที่แตกต่างกันเล็กน้อยระหว่างบริษัท ควรออกแบบให้ config ได้

---

## 8. Example Data / ตัวอย่างข้อมูลทดสอบ

### 8.1 ตัวอย่างใบสั่งขาย (SO6907-017)

ใช้ไฟล์ PDF นี้เป็นไฟล์ทดสอบหลัก:
- เลขที่: SO6907-017
- วันที่: 01/07/2569
- ลูกค้า: ย101609ยีสต์ กะ เนย (สำนักงานใหญ่)
- ที่อยู่: 23-25 ถนนจักรวรรดิ แขวงจักรวรรดิ เขตสัมพันธวงศ์ กรุงเทพมหานคร 10100
- สินค้า: CAKE (1 กล่อง), CREAM (2 กล่อง), CREAM 1x16 (3 กล่อง)
- PO: 295/14715

### 8.2 JSON Output ที่คาดหวังจาก Parser

```json
{
  "order_id": "SO6907-017",
  "customer_name": "ย101609ยีสต์ กะ เนย (สำนักงานใหญ่)",
  "delivery_address": "23-25 ถนนจักรวรรดิ แขวงจักรวรรดิ เขตสัมพันธวงศ์ กรุงเทพมหานคร 10100",
  "delivery_date": "2026-07-01",
  "po_reference": "295/14715",
  "items": [
    {
      "product_code": "92-0101",
      "product_name": "CAKE",
      "quantity": 1,
      "unit": "กล่อง",
      "weight_per_unit_kg": null
    },
    {
      "product_code": "91-0201",
      "product_name": "CREAM",
      "quantity": 2,
      "unit": "กล่อง",
      "weight_per_unit_kg": null
    },
    {
      "product_code": "91-0202",
      "product_name": "CREAM 1x16",
      "quantity": 3,
      "unit": "กล่อง",
      "weight_per_unit_kg": null
    }
  ],
  "total_quantity": 6,
  "total_boxes": 6,
  "source_file": "so6907-017.pdf",
  "parsed_at": "2026-07-28T12:04:00+07:00"
}
```

---

## 9. Success Metrics / ตัวชี้วัดความสำเร็จ

| Metric | Before | Target After |
|--------|--------|-------------|
| ความแม่นยำของ Parser (ดึงข้อมูลครบจาก PDF) | X% | > 95% |
| ออเดอร์ที่มีพิกัดผิด (จาก Report คนขับ) | X% | < 5% |
| ออเดอร์ที่ต้องแก้ไขพิกัดด้วยมือ | X% | < 10% |
| Confidence Score เฉลี่ย | X | > 85 |
| เวลาในการ Parse + Geocode + Validate ต่อออเดอร์ | X วินาที | < 3 วินาที |
| ค่าใช้จ่าย Map API ต่อเดือน | X บาท | ลดลง 30% (จาก Caching) |

---

> **หมายเหตุสำหรับผู้พัฒนา:** หากมีข้อสงสัยหรือต้องการตัวอย่างโค้ดเพิ่มเติมในส่วนใด สามารถขอได้เลย โดยเฉพาะส่วน OP Parser (PDF), Confidence Score Algorithm, Snap to Road Integration, หรือ Frontend Map Component
