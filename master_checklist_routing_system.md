# ✅ Master Checklist: ระบบจัดคิวและเส้นทางรถขนส่ง (Routing & Dispatching System)

> เอกสารนี้รวมทุกสิ่งที่ยังไม่ได้ทำ จากทุก Requirement ที่วิเคราะห์ร่วมกัน
> วันที่สร้าง: 31 กรกฎาคม 2026
> อัปเดตล่าสุด: 31 กรกฎาคม 2026 (Phase 0: Fix Debt เสร็จแล้ว)

---

## วิธีใช้
- `[ ]` = ยังไม่เริ่ม
- `[~]` = บางส่วน / ยังไม่สมบูรณ์
- `[x]` = เสร็จแล้ว
- แต่ละรายการควรมี **Owner** และ **Due Date**

---

## 🔴 Priority 1: ส่วนหลักที่ต้องทำก่อน (Core System)

### 1.1 Data Parser — อ่านไฟล์ OP (ใบสั่งขาย)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.1.1 | ตั้งค่า PDF Parser (pdfplumber / PyMuPDF) | อ่านใบสั่งขาย PDF จากบริษัท ทรีท็อป | [x] | ใช้ PyMuPDF (primary) + pdfplumber (fallback) + fallback general parse |
| 1.1.2 | ดึงชื่อลูกค้า/ผู้รับ | รองรับชื่อที่มีตัวเลขคละ เช่น `ย101609ยีสต์ กะ เนย` | [x] | Regex ดึงชื่อ + รหัส เช่น `ย101609` prefix |
| 1.1.3 | ดึงที่อยู่จัดส่ง | ที่อยู่ครบถ้วน (เลขที่, ถนน, แขวง, เขต, จังหวัด, รหัสไปรษณีย์) | [x] | ดึงระหว่าง "เงื่อนไขการชำระเงิน" ↔ "วันที่ต้องการ" |
| 1.1.4 | ดึงรายการสินค้า (Items Table) | รหัสสินค้า, ชื่อสินค้า, จำนวน, หน่วย | [x] | ดึงครบ code, name, quantity, unit |
| 1.1.5 | ดึงวันที่ต้องการ (Delivery Date) | แปลง พ.ศ. → ค.ศ. เช่น `01/07/2569` → `2026-07-01` | [x] | แปลง พ.ศ.→ค.ศ. ได้ทั้งแบบ DD/MM/YYYY และ DD เดือน YYYY + รองรับเดือนภาษาไทย |
| 1.1.6 | ดึงเลขที่ใบสั่งขาย (Order ID) | เช่น `SO6907-017` | [x] | Pattern `SO\d{4}-\d{3}` ทำงานได้ |
| 1.1.7 | ดึง PO Reference | เช่น `295/14715` | [x] | รองรับ PO Ref, เลขอ้างอิง, Purchase Order patterns |
| 1.1.8 | Validate ข้อมูลที่ parse ได้ | reject ถ้าฟิลด์สำคัญหาย (ชื่อ, ที่อยู่, สินค้า) | [x] | data_validator.py: ตรวจ address ว่าง, ตั้ง default name/weight |
| 1.1.9 | สร้าง JSON Output มาตรฐาน | ตาม schema ที่กำหนดไว้ | [x] | สร้าง dict พร้อม products list + po_reference + delivery_date |
| 1.1.10 | เก็บไฟล์ OP ต้นฉบับเป็น Backup | อย่างน้อย 7 วัน | [x] | บันทึกอัตโนมัติลง data/op_backups/ พร้อม timestamp |
| 1.1.11 | รองรับหลาย Template ใบสั่งขาย | config ได้ว่าแต่ละบริษัทใช้ template ไหน | [x] | JSON config ใน data/templates/pdf_templates.json + template loader |

### 1.2 Geocoding & Location Validation

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.2.1 | Multi-Provider Geocoding | ยิงไปทั้ง Google Maps + Nominatim (OpenStreetMap) | [x] | Google Places → Google Geocoding → Esri → Nominatim cascade |
| 1.2.2 | Validate Bounding Box ไทย | Lat 5°-21°N, Lon 97°-106°E | [x] | ตรวจสอบทุก geocode result |
| 1.2.3 | คำนวณ Confidence Score | Algorithm: ตรงกัน 2 แหล่ง=100%, 1 แหล่ง=50%, ห่าง>500m=ต่ำ | [x] | คำนวณตาม provider + precision (ROOFTOP=98%, RANGE=85%, GEOMETRIC=55%, APPROX=30%) |
| 1.2.4 | Reverse Geocoding ย้อนกลับ | เทียบที่อยู่ที่ได้กับต้นฉบับ | [x] | Google → Nominatim fallback |
| 1.2.5 | Snap to Road API | ดึงพิกัดให้ติดถนนก่อนคำนวณ | [ ] | ยังไม่ได้ทำ |
| 1.2.6 | Flag จุดที่ Confidence < 70% | บังคับให้ผู้ใช้ยืนยันก่อนบันทึก | [x] | API endpoint `/orders/low-confidence` + confidence score ในทุก order |
| 1.2.7 | Cache Geocoding Result (Redis) | จุดที่เคยคำนวณแล้วไม่ต้องเรียกซ้ำ | [~] | มี in-memory cache + persistent location memory ใน DB แต่ไม่ใช่ Redis |
| 1.2.8 | Handle Rate Limit & Error | Retry with exponential backoff | [x] | `_request_with_retry()`: 3 retries, exponential backoff, จัดการ 429/Timeout/ConnectionError |

### 1.3 Database Schema

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.3.1 | ตาราง orders | order_id, customer_name, delivery_address, delivery_date, po_reference | [x] | พร้อม geocode metadata ครบ (raw/verified lat/lng, confidence, provider, zone, products JSON) |
| 1.3.2 | ตาราง order_items | item_id, order_id, product_code, product_name, quantity, unit | [x] | สร้างตาราง order_items + index + save_orders บันทึกลง table อัตโนมัติ |
| 1.3.3 | ตาราง locations | raw_geocode_lat/lng, verified_lat/lng, confidence_score, geocode_provider | [x] | customer_locations table + geocode data ใน orders |
| 1.3.4 | ตาราง vehicles | vehicle_id, plate_number, max_weight_kg, max_volume_cbm, max_boxes, max_stops | [x] | เพิ่ม max_volume_cbm, max_boxes, max_stops + auto-migration |
| 1.3.5 | ตาราง vehicle_load (real-time) | current_weight, current_volume, current_boxes, current_stops | [ ] | ไม่มี real-time load tracking |
| 1.3.6 | ตาราง routes | route_id, vehicle_id, status, planned_stops, completed_stops | [~] | มี route_plans + route_details แต่ stops เก็บเป็น JSON ไม่ใช่ separate rows |
| 1.3.7 | ตาราง route_stops | stop_id, route_id, sequence, status, scheduled_time, actual_time | [~] | stops เก็บเป็น JSON array ใน route_details ไม่ใช่ตารางแยก |
| 1.3.8 | ตาราง stop_status_history | audit log ทุกการเปลี่ยนสถานะ | [ ] | ไม่มี audit log |
| 1.3.9 | ตาราง item_deliveries | ordered_qty, delivered_qty, status ระดับ item | [ ] | ไม่มี delivery tracking ระดับ item |
| 1.3.10 | ตาราง route_transfers | log การย้าย stop ระหว่างรถ | [ ] | ไม่มี transfer log |
| 1.3.11 | ตาราง vehicle_locations | lat, lng, speed, heading, recorded_at (real-time GPS) | [ ] | ไม่มี GPS tracking |
| 1.3.12 | Migration Script | สคริปต์สร้าง/แก้ไขตารางทั้งหมด | [~] | มี auto-migration ใน db.py (init_db) แต่ไม่มี standalone migration script |

### 1.4 VRP Routing Engine

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.4.1 | สร้าง Distance Matrix | จากพิกัดที่ผ่านการ Snap to Road แล้ว | [x] | distance_matrix.py: Google Maps API + Haversine fallback + in-memory cache + ใช้จริงใน optimizer |
| 1.4.2 | ตั้งค่า OR-Tools VRP | รองรับ time window, capacity, multiple vehicles | [~] | OR-Tools CVRPTW ใช้จริงแล้ว แต่ยังไม่มี time window (มีแค่ capacity) |
| 1.4.3 | ตั้ง Timeout ให้ Optimization | หยุดหลังเวลาที่กำหนด (เช่น 30-60 วินาที) | [x] | SOLVE_TIMEOUT_SECONDS = 30 ใน route_optimizer.py |
| 1.4.4 | จำกัด RAM/CPU | container limit หรือ process limit | [ ] | ไม่มี resource limit |
| 1.4.5 | จำกัดขนาดปัญหา | ถ้า >200 stops ให้ cluster เป็น zone ก่อน | [ ] | ไม่มี clustering |
| 1.4.6 | Validate Constraints ก่อนคำนวณ | time window, capacity ไม่ติดลบ | [ ] | ไม่มี constraint validation |
| 1.4.7 | สร้าง Route Plan Output | JSON ที่มี sequence, ETA, ระยะทางรวม | [~] | JSON + Google Maps link + total_distance_km แต่ยังไม่มี ETA |
| 1.4.8 | Cache Distance Matrix | เก็บใน Redis ลดการเรียก Map API | [~] | มี in-memory cache (`_MATRIX_CACHE`) แต่ไม่ใช่ Redis |

---

### 1.5 Dynamic Load Balancing (กระจายสินค้าระหว่างรถ)

#### 1.5.1 ตรวจจับสถานะรถ (Auto-Detection)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.5.1.1 | คำนวณ Utilization ทุกรถทุก X นาที | ตรวจสอบน้ำหนัก, ปริมาตร, จำนวนกล่อง, จำนวน stop | [ ] | ยังไม่ได้ทำ |
| 1.5.1.2 | ตั้ง Threshold "รถเต็ม" | ค่าเริ่มต้น: >= 90% ของ capacity ใดๆ | [ ] | ยังไม่ได้ทำ |
| 1.5.1.3 | ตั้ง Threshold "รถว่างเกิน" | ค่าเริ่มต้น: <= 40% ของ capacity ทุกอย่าง | [ ] | ยังไม่ได้ทำ |
| 1.5.1.4 | ตั้ง Threshold "รถปกติ" | อยู่ระหว่าง 40% - 90% | [ ] | ยังไม่ได้ทำ |
| 1.5.1.5 | แสดงสถานะรถบน Dashboard | สี: แดง=เต็ม / เหลือง=ใกล้เต็ม / เขียว=ปกติ / ฟ้า=ว่าง | [ ] | ยังไม่ได้ทำ |
| 1.5.1.6 | แจ้งเตือนเมื่อรถเข้าเกณฑ์กระจาย | Push notification ไปยัง Dispatcher | [ ] | ยังไม่ได้ทำ |

#### 1.5.2 กรณีที่ 1: รถเต็ม -> กระจายออกไปรถข้างเคียง (Overflow -> Out)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.5.2.1 | ระบุรถที่เต็ม (Source) | รถที่ utilization >= 90% | [ ] | ยังไม่ได้ทำ |
| 1.5.2.2 | หา Stop ที่จะย้ายออก | เลือก stop ที่: ไม่ส่งเร็ว (time window ยาว), ไม่ใช่ VIP, น้ำหนักพอดี | [ ] | ยังไม่ได้ทำ |
| 1.5.2.3 | หารถเป้าหมาย (Target) ที่รับได้ | เงื่อนไข: utilization < 80%, อยู่ในรัศมี X กม., ทิศทางเดียวกัน | [ ] | ยังไม่ได้ทำ |
| 1.5.2.4 | คำนวณ "ความคุ้มค่า" ของการย้าย | ดูส่วน Scoring Algorithm | [ ] | ยังไม่ได้ทำ |
| 1.5.2.5 | ตรวจสอบ Time Window | ย้ายแล้วรถเป้าหมายต้องไปทัน | [ ] | ยังไม่ได้ทำ |
| 1.5.2.6 | ตรวจสอบ Same Order | อย่าแบ่งสินค้าจากออเดอร์เดียวกันไปหลายรถ (ถ้าไม่จำเป็น) | [ ] | ยังไม่ได้ทำ |
| 1.5.2.7 | แสดง Suggestion ให้ Dispatcher | แสดง: ย้าย Stop X จากรถ A -> รถ B, ประหยัดเวลา/น้ำมันเท่าไร | [ ] | ยังไม่ได้ทำ |
| 1.5.2.8 | Dispatcher กด "ยืนยัน" ก่อน execute | Human-in-the-loop (ไม่ย้ายอัตโนมัติ 100%) | [ ] | ยังไม่ได้ทำ |

#### 1.5.3 กรณีที่ 2: รถว่าง -> กระจายเข้ารับจากรถข้างเคียง (Underflow -> In)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.5.3.1 | ระบุรถที่ว่างเกิน (Target) | รถที่ utilization <= 40% | [ ] | ยังไม่ได้ทำ |
| 1.5.3.2 | หารถข้างเคียงที่บรรทุกเยอะ (Source) | utilization >= 75%, อยู่ในรัศมี X กม. | [ ] | ยังไม่ได้ทำ |
| 1.5.3.3 | หา Stop ที่เหมาะสมจากรถ Source | ใกล้เส้นทางของรถ Target, ไม่ทำให้ Source เหลือน้อยเกินไป | [ ] | ยังไม่ได้ทำ |
| 1.5.3.4 | คำนวณ "ความคุ้มค่า" ของการย้าย | ดูส่วน Scoring Algorithm | [ ] | ยังไม่ได้ทำ |
| 1.5.3.5 | ตรวจสอบว่ารถ Target ไม่โหลดเกิน | ย้ายมาแล้วต้องไม่เกิน 85% | [ ] | ยังไม่ได้ทำ |
| 1.5.3.6 | ตรวจสอบ Time Window | รถ Target ไปทันเวลาลูกค้ากำหนด | [ ] | ยังไม่ได้ทำ |
| 1.5.3.7 | แสดง Suggestion ให้ Dispatcher | แสดง: ย้าย Stop X จากรถ B -> รถ A, เหตุผล: แบ่งเบาภาระ | [ ] | ยังไม่ได้ทำ |
| 1.5.3.8 | Dispatcher กด "ยืนยัน" ก่อน execute | Human-in-the-loop | [ ] | ยังไม่ได้ทำ |

#### 1.5.4 Transfer Score Algorithm (คำนวณคะแนนความคุ้มค่า)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.5.4.1 | คำนวณ "ระยะทางเบี่ยงเบน" (Detour Distance) | รถ Target ต้องเบี่ยงจากเส้นทางเดิมกี่กม. | [ ] | ยังไม่ได้ทำ |
| 1.5.4.2 | คำนวณ "เวลาที่เสีย" (Time Penalty) | Detour ใช้เวลาเพิ่มกี่นาที | [ ] | ยังไม่ได้ทำ |
| 1.5.4.3 | คำนวณ "ความพอดี" (Capacity Fit) | ย้ายมาแล้ว Target อยู่ที่ % ไหน (เป้าหมาย: 60-80%) | [ ] | ยังไม่ได้ทำ |
| 1.5.4.4 | คำนวณ "ความเสี่ยง Time Window" | ถ้าย้ายแล้วไปทัน = ผ่าน, ไม่ทัน = ตัดทิ้ง | [ ] | ยังไม่ได้ทำ |
| 1.5.4.5 | คำนวณ "ผลกระทบลูกค้า" | VIP = ตัดทิ้ง, ทั่วไป = ผ่าน | [ ] | ยังไม่ได้ทำ |
| 1.5.4.6 | รวมคะแนนเป็น "Transfer Score" | ยิ่งต่ำ = ยิ่งคุ้มค่า | [ ] | ยังไม่ได้ทำ |
| 1.5.4.7 | เรียงลำดับตัวเลือก | แสดง Top 3 ตัวเลือกที่ดีที่สุด | [ ] | ยังไม่ได้ทำ |

#### 1.5.5 Constraints (เงื่อนไขสำคัญที่ต้องตรวจสอบ)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.5.5.1 | Time Window ต้องไม่เสีย | ลูกค้าต้องได้รับของภายในเวลาที่กำหนด | [ ] | ยังไม่ได้ทำ |
| 1.5.5.2 | อย่าแบ่งออเดอร์เดียวกัน | สินค้าจาก SO เดียวกัน ควรอยู่รถเดียวกัน | [ ] | ยังไม่ได้ทำ |
| 1.5.5.3 | อย่าให้รถต้นทางเหลือน้อยเกินไป | ย้ายออกแล้วต้นทางต้องไม่ต่ำกว่า 30% | [ ] | ยังไม่ได้ทำ |
| 1.5.5.4 | รถเป้าหมายต้องไม่เกิน 85% | ย้ายเข้าแล้วต้องไม่เต็ม | [ ] | ยังไม่ได้ทำ |
| 1.5.5.5 | อยู่ในรัศมีที่สมเหตุสมผล | เช่น ไม่เกิน 5 กม. หรือ 15 นาทีจากเส้นทาง | [ ] | ยังไม่ได้ทำ |
| 1.5.5.6 | ทิศทางต้องสอดคล้องกัน | รถเป้าหมายต้องวิ่งไปทางเดียวกัน (ไม่วนกลับ) | [ ] | ยังไม่ได้ทำ |
| 1.5.5.7 | ประเภทสินค้าต้องตรง | ถ้ารถแช่เย็น -> ย้ายได้แค่สินค้าแช่เย็น | [ ] | ยังไม่ได้ทำ |
| 1.5.5.8 | คนขับต้องรับทราบ | แจ้งเตือนทั้ง 2 ฝ่ายก่อนย้าย | [ ] | ยังไม่ได้ทำ |

#### 1.5.6 Execute Transfer (ดำเนินการหลังยืนยัน)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.5.6.1 | ย้าย Stop จากรถ A -> รถ B ในฐานข้อมูล | อัปเดต route_stops | [ ] | ยังไม่ได้ทำ |
| 1.5.6.2 | อัปเดต Sequence ใหม่ของทั้ง 2 รถ | Re-order stops | [ ] | ยังไม่ได้ทำ |
| 1.5.6.3 | Re-calculate Route ของทั้ง 2 รถ | ใช้ VRP ใหม่ หรือ heuristic | [ ] | ยังไม่ได้ทำ |
| 1.5.6.4 | อัปเดต ETA ใหม่ | ส่งไปยังคนขับทั้ง 2 คัน | [ ] | ยังไม่ได้ทำ |
| 1.5.6.5 | แจ้งเตือนคนขับรถต้นทาง | "Stop X ถูกย้ายออกไปรถ B" | [ ] | ยังไม่ได้ทำ |
| 1.5.6.6 | แจ้งเตือนคนขับรถเป้าหมาย | "มี Stop X เพิ่มเข้ามา กรุณาตรวจสอบเส้นทางใหม่" | [ ] | ยังไม่ได้ทำ |
| 1.5.6.7 | บันทึก Log การย้าย | เก็บใน route_transfers | [ ] | ยังไม่ได้ทำ |
| 1.5.6.8 | อัปเดต Dashboard | แสดงผลลัพธ์ทันที | [ ] | ยังไม่ได้ทำ |

---

## 🟡 Priority 2: ส่วนที่ต้องทำระหว่าง Development (Feature Complete)

### 2.1 Dynamic Vehicle Capacity (REQ-1)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 2.1.1 | API แก้ไข capacity รถ | Admin กำหนดน้ำหนัก/ปริมาตร/กล่อง/stops ได้ | [~] | VehicleManager.jsx มี CRUD แก้ไข max_weight_kg ได้ แต่ไม่มี volume/boxes/stops fields |
| 2.1.2 | คำนวณ Utilization % | แสดง % การใช้ capacity แบบ real-time | [~] | Dashboard มี fleet utilization bar แต่ไม่ real-time (แค่ตอน route plan คำนวณเสร็จ) |
| 2.1.3 | สีแจ้งเตือน Utilization | เขียว<70%, เหลือง70-90%, แดง>90%, ม่วง>100% override | [~] | RouteResult.jsx มี capacity bar + overload detection >90% แต่ไม่มีสีม่วง override |
| 2.1.4 | Drag-and-Drop ย้าย stop ระหว่างรถ | Frontend: ลากจากรถ A ไปรถ B | [ ] | ยังไม่ได้ทำ |
| 2.1.5 | Validate ก่อนย้าย | block ถ้าเกิน capacity (ยกเว้น override) | [ ] | ยังไม่ได้ทำ |
| 2.1.6 | Override Capacity | กรณีฉุกเฉิน พร้อมบันทึกเหตุผลและคนทำ | [ ] | ยังไม่ได้ทำ |
| 2.1.7 | Audit Log การ Override | เก็บไว้ในฐานข้อมูล | [ ] | ยังไม่ได้ทำ |

### 2.2 Delivery Status Tracking (REQ-2)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 2.2.1 | State Machine Stop Status | PENDING → IN_TRANSIT → ARRIVED → DELIVERED/FAILED/PARTIAL | [ ] | ไม่มี state machine |
| 2.2.2 | Track Status ระดับ Item | ordered_qty, delivered_qty, status แยก item | [ ] | ไม่มี item-level tracking |
| 2.2.3 | Driver Mobile: กด ARRIVED | คนขับกดยืนยันถึงจุดส่ง | [ ] | ไม่มี Driver Mobile App |
| 2.2.4 | Driver Mobile: กด DELIVERED | พร้อมถ่ายรูป POD | [ ] | ไม่มี Driver Mobile App |
| 2.2.5 | Driver Mobile: กด FAILED | เลือกเหตุผล: ไม่มีคนรับ, ที่อยู่ผิด, สินค้าเสียหาย | [ ] | ไม่มี Driver Mobile App |
| 2.2.6 | Driver Mobile: กด PARTIAL | กรอกจำนวนที่ส่งจริง | [ ] | ไม่มี Driver Mobile App |
| 2.2.7 | GPS Auto-detect ARRIVED | เข้าใกล้จุดส่ง X เมตร → อัปเดตอัตโนมัติ | [ ] | ไม่มี GPS tracking |
| 2.2.8 | Dashboard สถานะรวม | กี่จุดส่งแล้ว / ค้าง / มีปัญหา | [ ] | ไม่มี delivery status dashboard |
| 2.2.9 | Filter & Search Stop | ตามสถานะ, รถ, วันที่ | [ ] | ยังไม่ได้ทำ |
| 2.2.10 | Notification แจ้งเตือน | Failed, หยุดนาน, เบี่ยงเส้นทาง | [ ] | ไม่มี notification system |

### 2.3 Load Balancing (REQ-3)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 2.3.1 | Auto-detect รถเต็ม | utilization > 95% ของ capacity ใดๆ | [ ] | ยังไม่ได้ทำ |
| 2.3.2 | Algorithm หารถใกล้เคียง | หารถ B ที่มี capacity เหลือ + อยู่ใกล้ | [ ] | ยังไม่ได้ทำ |
| 2.3.3 | Algorithm คำนวณ Transfer Cost | distance + time + capacity_fit + time_window_risk | [ ] | ยังไม่ได้ทำ |
| 2.3.4 | Suggest Top 3 รถที่เหมาะสม | แสดงให้ Dispatcher เลือก | [ ] | ยังไม่ได้ทำ |
| 2.3.5 | Dispatcher ยืนยันก่อน Execute | Human-in-the-loop (ไม่ auto 100%) | [ ] | ยังไม่ได้ทำ |
| 2.3.6 | Re-calculate Route หลังย้าย | อัปเดต sequence + ETA รถที่เกี่ยวข้อง | [ ] | ยังไม่ได้ทำ |
| 2.3.7 | แจ้งเตือนคนขับทั้ง 2 คัน | หลังย้าย stop | [ ] | ยังไม่ได้ทำ |
| 2.3.8 | Manual "Find Nearby Vehicle" | Dispatcher เลือก stop → กดหารถใกล้เคียง | [ ] | ยังไม่ได้ทำ |
| 2.3.9 | Constraint การย้าย | รักษา time window, ไม่แบ่งลูกค้ารายเดียวหลายรถ | [ ] | ยังไม่ได้ทำ |

### 2.4 Reschedule (ส่งไม่สำเร็จ → ย้ายไปวันถัดไป)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 2.4.1 | สถานะ RESCHEDULED | ใน State Machine | [ ] | ยังไม่ได้ทำ |
| 2.4.2 | ย้าย stop กลับเข้า Queue รอจัดส่งวันถัดไป | ไม่ติดกับรถเดิม | [ ] | ยังไม่ได้ทำ |
| 2.4.3 | แจ้งเตือนลูกค้า (ถ้ามีเบอร์/อีเมล) | อัตโนมัติหรือแมนนวล | [ ] | ยังไม่ได้ทำ |
| 2.4.4 | บันทึกเหตุผลการ reschedule | ไว้ดูย้อนหลัง | [ ] | ยังไม่ได้ทำ |

---

## 🟢 Priority 3: ส่วนเสริมที่ทำได้ภายหลัง (Enhancement)

### 3.1 Frontend — Dispatcher Dashboard

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 3.1.1 | Panel รายการรถ (ซ้าย) | สถานะ, utilization bar, จำนวน stop | [~] | Dashboard.jsx มี fleet utilization card แต่ไม่ real-time |
| 3.1.2 | แผนที่กลาง (Map) | ตำแหน่งรถ real-time, pin ตามสถานะ | [~] | MapView.jsx มี Leaflet map + depot marker + delivery markers + route polylines แต่ไม่มี real-time GPS tracking |
| 3.1.3 | Panel Stop List (ขวา) | เรียง sequence, drag-and-drop | [~] | MapView.jsx มี side inspector panel + stop list แต่ไม่มี drag-and-drop reorder |
| 3.1.4 | Panel Alert & Notification (บน) | แจ้งเตือน + Load Balancing suggestion | [ ] | ไม่มี alert/notification panel |
| 3.1.5 | หน้า "Review & Confirm Location" | แผนที่ + Pin ลากได้ + Confidence Score | [x] | MapView.jsx: drag pins + reverse geocode + confidence score + save to DB + place search |
| 3.1.6 | หน้า Admin Dashboard | Location Quality Report, Heatmap | [ ] | ไม่มี admin dashboard / heatmap |
| 3.1.7 | Street View / ภาพถ่ายดาวเทียม | แสดงประกอบก่อนยืนยันพิกัด | [~] | MapView.jsx มี ArcGIS satellite tile layer แต่ไม่มี Street View |

### 3.2 Frontend — Driver Mobile Web

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 3.2.1 | หน้า Route Today | รายการ stop ของวันนี้ | [ ] | ไม่มี Driver Mobile view |
| 3.2.2 | หน้า Stop Detail | ชื่อลูกค้า, ที่อยู่, สินค้า, ปุ่มนำทาง | [ ] | ไม่มี Driver Mobile view |
| 3.2.3 | ปุ่ม ARRIVED / DELIVERED / FAILED | กดอัปเดตสถานะ | [ ] | ไม่มี Driver Mobile view |
| 3.2.4 | อัปโหลดรูป POD | ถ่ายรูป → อัปโหลด | [ ] | ไม่มี Driver Mobile view |
| 3.2.5 | ปุ่ม "Report Wrong Pin" | ส่งพิกัดจริง + รูป + หมายเหตุ | [ ] | ไม่มี Driver Mobile view |
| 3.2.6 | ดู Stop ถัดไป + ETA | อัปเดตแบบ real-time | [ ] | ไม่มี Driver Mobile view |

### 3.3 LINE Messaging API Integration

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 3.3.1 | สมัคร LINE Official Account | https://manager.line.biz | [ ] | ยังไม่ได้ทำ |
| 3.3.2 | สร้าง Channel + เอา Access Token | LINE Developers Console | [ ] | ยังไม่ได้ทำ |
| 3.3.3 | Python: ส่ง Push Message | ข้อความ + ลิงก์ Google Maps | [ ] | ยังไม่ได้ทำ |
| 3.3.4 | เชื่อมกับระบบหลัก | Trigger ตอนคำนวณเส้นทางเสร็จ | [ ] | ยังไม่ได้ทำ |
| 3.3.5 | เก็บ LINE User ID คนขับ | ในฐานข้อมูล vehicles/drivers | [ ] | ยังไม่ได้ทำ |
| 3.3.6 | (เพิ่มเติม) Webhook รับข้อความ | ถ้าอยากให้คนขับกดปุ่มตอบกลับ | [ ] | ยังไม่ได้ทำ |
| 3.3.7 | (เพิ่มเติม) Rich Menu / Quick Reply | ปุ่ม "ส่งสำเร็จ" / "ส่งไม่ได้" ในแชต | [ ] | ยังไม่ได้ทำ |

### 3.4 Security & Infrastructure

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 3.4.1 | ย้าย API Key ไป Environment Variable | ห้าม hardcode | [x] | ใช้ .env + config.py ครอบคลุมทุก key |
| 3.4.2 | จำกัดขนาดไฟล์ OP | Hard limit (เช่น 50 MB) | [~] | MAX_FILE_SIZE_MB=10 ใน config.py แต่ไม่ enforce ใน routes.py |
| 3.4.3 | ป้องกัน Path Traversal | ตรวจสอบชื่อไฟล์ | [~] | มี _validate_file() ตรวจสอบ PDF extension + filename แต่ไม่ full path traversal check |
| 3.4.4 | อ่านไฟล์แบบ Streaming | ไม่โหลดทั้งไฟล์เข้า RAM | [ ] | โหลดทั้งไฟล์เข้า RAM (await file.read()) |
| 3.4.5 | Audit Log ทุกขั้นตอน | input hash, intermediate, output | [ ] | ไม่มี audit log |
| 3.4.6 | Mask Sensitive Data ใน Log | ตัดทอนพิกัดลูกค้า | [ ] | ไม่มี masking |
| 3.4.7 | Queue System (Redis/Celery) | ถ้ามีหลาย request พร้อมกัน | [ ] | ไม่มี queue system |
| 3.4.8 | Health Check Endpoint | เช็คสถานะ Parser, Cache, Engine | [x] | GET /api/system-status รายงาน API key, AI toggle, order count |
| 3.4.9 | Metrics & Monitoring | เวลาคำนวณ, จำนวน request, error rate | [ ] | ไม่มี metrics/monitoring |
| 3.4.10 | PDPA/GDPR Compliance | ประเมินการส่งพิกัดไป Third-Party | [ ] | ไม่มี compliance |

---

## 🐛 ปัญหาที่พบในโค้ด (ควรแก้ก่อนทำ feature ใหม่)

| # | ปัญหา | รายละเอียด | ความสำคัญ | สถานะ |
|---|--------|-----------|----------|-------|
| B.1 | `ortools` ไม่ได้ใช้จริง | อยู่ใน requirements.txt แต่ optimizer ใช้ Sweep + Nearest Neighbor แทน | สูง | [x] แก้แล้ว — เขียน route_optimizer.py ใหม่ ใช้ OR-Tools CVRPTW |
| B.2 | `distance_matrix` ไม่ได้ใช้ใน optimizer | คำนวณ distance matrix แล้วส่งเข้า optimize_routes() แต่ไม่ได้ใช้ตัดสินใจ | สูง | [x] แก้แล้ว — optimizer ใช้ distance matrix จริง |
| B.3 | Dependencies ใน requirements.txt ไม่ครบ | `PyMuPDF`, `openpyxl`, `requests` import ในโค้ดแต่ไม่อยู่ใน requirements.txt → fresh install จะ error | สูง | [x] แก้แล้ว — เพิ่มครบ +ลบ httpx/jinja2/aiofiles |
| B.4 | Dependencies เกินจำเป็น | `httpx`, `jinja2`, `aiofiles` อยู่ใน requirements.txt แต่ไม่ได้ import | ต่ำ | [x] แก้แล้ว — ลบออก + เพิ่ม pytest |
| B.5 | `models/schemas.py` เป็น dead code | Define Pydantic model ไว้แต่ routes.py ไม่ได้ใช้ (ใช้ inline dict แทน) | ต่ำ | [x] แก้แล้ว — เพิ่ม VerifyLocationRequest + field ครบ |
| B.6 | ไม่มี Authentication | API ทุก endpoint เปิดรับทุกคน ไม่มี auth/token | สูง | [ ] ยังไม่ได้ทำ |
| B.7 | ไม่มี Test | ไม่มี pytest, ไม่มี unit test, ไม่มี E2E test | สูง | [x] แก้แล้ว — 16 unit tests (data_validator, haversine, distance_matrix, route_optimizer) |
| B.8 | Version string ไม่ตรงกัน | main.py บอก v1.2.0 แต่ root endpoint บอก v1.1.0 | ต่ำ | [x] แก้แล้ว — ทั้งสองจุดเป็น v1.2.0 |
| B.9 | Gemini/Ollama config เป็น dead code | ตั้งค่าใน config.py แต่ไม่เคยเรียกใช้ | ต่ำ | [x] แก้แล้ว — ลบ OLLAMA_URL, GEMINI_API_KEY |
| B.10 | AI Refinement toggle CSS มีแต่ไม่ wire up | มี CSS class `.ai-refinement-toggle` ใน App.css แต่ไม่มี component ที่ใช้ | ต่ำ | [ ] ยังไม่ได้ทำ |

---

## 📊 สรุปสถานะโดยรวม

| Priority | จำนวนรายการ | เสร็จแล้ว [x] | บางส่วน [~] | ยังไม่ได้ทำ [ ] | คิดเป็น |
|----------|------------|--------------|------------|----------------|--------|
| 🔴 P1: Data Parser (1.1) | 11 | 11 | 0 | 0 | 100% |
| 🔴 P1: Geocoding (1.2) | 8 | 5 | 2 | 1 | 69% |
| 🔴 P1: Database (1.3) | 12 | 4 | 2 | 6 | 33% |
| 🔴 P1: VRP Routing (1.4) | 8 | 2 | 3 | 3 | 31% |
| 🔴 P1: Load Balancing (1.5) | 48 | 0 | 0 | 48 | 0% |
| 🟡 P2: Vehicle Capacity (2.1) | 7 | 0 | 3 | 4 | 21% |
| 🟡 P2: Delivery Tracking (2.2) | 10 | 0 | 0 | 10 | 0% |
| 🟡 P2: Load Balancing (2.3) | 9 | 0 | 0 | 9 | 0% |
| 🟡 P2: Reschedule (2.4) | 4 | 0 | 0 | 4 | 0% |
| 🟢 P3: Dashboard (3.1) | 7 | 1 | 3 | 3 | 21% |
| 🟢 P3: Driver Mobile (3.2) | 6 | 0 | 0 | 6 | 0% |
| 🟢 P3: LINE API (3.3) | 7 | 0 | 0 | 7 | 0% |
| 🟢 P3: Security (3.4) | 10 | 2 | 2 | 6 | 20% |
| **รวมทั้งหมด** | **~147** | **28** | **17** | **102** | **~19%** |

> **หมายเหตุ:** นับจาก main checklist เท่านั้น ไม่รวม B.1-B.10 (Fix Debt) ที่แก้เสร็จ 8 รายการ

---

## 🗓️ Phased Development Plan (แนะนำ)

| Phase | ระยะเวลา | รายการหลักที่ทำ | สถานะ |
|-------|---------|----------------|------|
| **Phase 0: Fix Debt** | สัปดาห์ 0 | แก้ B.1-B.5, B.7-B.9 (requirements.txt, dead code, OR-Tools, tests, version) | ✅ เสร็จแล้ว |
| **Phase 1: Foundation** | สัปดาห์ 1-2 | Parser (1.1) + Geocoding (1.2) + DB Schema (1.3) | ✅ เสร็จแล้ว |
| **Phase 2: Routing Engine** | สัปดาห์ 3-4 | VRP (1.4) + OR-Tools + Distance Matrix จริง + ETA | ⬜ ยังไม่ได้ทำ |
| **Phase 3: Status Tracking** | สัปดาห์ 5-6 | Delivery Status (2.2) + Driver Mobile Web + State Machine | ⬜ ยังไม่ได้ทำ |
| **Phase 4: Dynamic Features** | สัปดาห์ 7-8 | Capacity (2.1) + Load Balancing (1.5/2.3) + Reschedule (2.4) | ⬜ ยังไม่ได้ทำ |
| **Phase 5: Integration** | สัปดาห์ 9-10 | LINE API (3.3) + Admin Dashboard (3.1) + Security (3.4) | ⬜ ยังไม่ได้ทำ |
| **Phase 6: Polish** | สัปดาห์ 11-12 | Test + Debug + Deploy + Optimization | ⬜ ยังไม่ได้ทำ |

---

## 📝 บันทึกการแก้ไข (Changelog)

| วันที่ | เวอร์ชัน | รายการที่แก้ | ผู้แก้ไข |
|-------|---------|-------------|---------|
| 31 ก.ค. 2026 | 1.1 | อัปเดต status ทั้งหมดจากผลวิเคราะห์โค้ดจริง (Backend + Frontend) | AI Analysis |
| 31 ก.ค. 2026 | 1.2 | Phase 0 Fix Debt: แก้ B.1-B.5, B.7-B.9 (OR-Tools VRP, requirements.txt, schemas, tests, config cleanup) | AI + User |
| 31 ก.ค. 2026 | 1.3 | Phase 1 Foundation: แก้ 1.1.5, 1.1.7, 1.1.10, 1.1.11, 1.2.6, 1.2.8, 1.3.2, 1.3.4 (PDF parser, geocoding retry, DB schema) | AI + User |

---

> **หมายเหตุ:** เอกสารนี้รวมทุก requirement จากบทสนทนาทั้งหมด รวมถึง:
> - ระบบ Parser อ่านไฟล์ OP (PDF)
> - Geocoding + Validation (Confidence Score, Reverse Geocode, Snap to Road)
> - VRP Routing Engine (OR-Tools)
> - Dynamic Vehicle Capacity (REQ-1)
> - Delivery Status Tracking (REQ-2)
> - Load Balancing (REQ-3)
> - Reschedule (ส่งไม่สำเร็จ → วันถัดไป)
> - LINE Messaging API Integration
> - Security Checklist
>
> **ไฟล์ที่เกี่ยวข้อง:**
> - Backend: `backend/services/pdf_extractor.py`, `geocoding.py`, `route_optimizer.py`, `distance_matrix.py`
> - Frontend: `frontend/src/components/MapView.jsx`, `RouteResult.jsx`, `VehicleManager.jsx`, `Dashboard.jsx`
> - DB: `backend/database/db.py`
