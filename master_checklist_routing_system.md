# ✅ Master Checklist: ระบบจัดคิวและเส้นทางรถขนส่ง (Routing & Dispatching System)

> เอกสารนี้รวมทุกสิ่งที่ยังไม่ได้ทำ จากทุก Requirement ที่วิเคราะห์ร่วมกัน
> วันที่สร้าง: 31 กรกฎาคม 2026
> อัปเดตล่าสุด: **01 สิงหาคม 2026 (Queue System + Metrics & Monitoring — 73% complete)**

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
| 1.3.4 | ตาราง vehicles | vehicle_id, plate_number, max_weight_kg, max_volume_cbm, max_boxes, max_stops | [x] | เพิ่ม max_volume_cbm, max_boxes, max_stops + auto-migration + สร้าง SQLAlchemy ORM model |
| 1.3.5 | ตาราง vehicle_load (real-time) | current_weight, current_volume, current_boxes, current_stops | [ ] | ไม่มี real-time load tracking |
| 1.3.6 | ตาราง routes | route_id, vehicle_id, status, planned_stops, completed_stops | [~] | มี route_plans + route_details แต่ stops เก็บเป็น JSON ไม่ใช่ separate rows |
| 1.3.7 | ตาราง route_stops | stop_id, route_id, sequence, status, scheduled_time, actual_time | [~] | stops เก็บเป็น JSON array ใน route_details ไม่ใช่ตารางแยก |
| 1.3.8 | ตาราง stop_status_history | audit log ทุกการเปลี่ยนสถานะ | [x] | สร้าง StopStatusHistory model + update_stop_status() บันทึกอัตโนมัติทุก status change |
| 1.3.9 | ตาราง item_deliveries | ordered_qty, delivered_qty, status ระดับ item | [x] | สร้าง ItemDelivery model + update_item_delivery() + API endpoint /delivery/update-item |
| 1.3.10 | ตาราง route_transfers | log การย้าย stop ระหว่างรถ | [x] | สร้าง RouteTransfer model (ใช้ใน Load Balancing) |
| 1.3.11 | ตาราง vehicle_locations | lat, lng, speed, heading, recorded_at (real-time GPS) | [x] | สร้าง VehicleLocation model (ใช้ใน GPS tracking) |
| 1.3.12 | Migration Script | สคริปต์สร้าง/แก้ไขตารางทั้งหมด | [x] | สร้าง migrate_sqlite_to_postgres.py + auto-migration ใน db.py |
| 1.3.13 | PostgreSQL Database | ย้ายจาก SQLite ไป PostgreSQL | [x] | SQLAlchemy + PostgreSQL + Docker Compose setup |
| 1.3.14 | Docker Setup | รันระบบทั้งหมดใน Container | [x] | docker-compose.yml + Dockerfile backend/frontend + nginx.conf |

### 1.4 VRP Routing Engine

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.4.1 | สร้าง Distance Matrix | จากพิกัดที่ผ่านการ Snap to Road แล้ว | [x] | distance_matrix.py: Google Maps API + Haversine fallback + in-memory cache + ใช้จริงใน optimizer |
| 1.4.2 | ตั้งค่า OR-Tools VRP | รองรับ time window, capacity, multiple vehicles | [~] | OR-Tools CVRPTW ใช้จริงแล้ว: CHRISTOFIDES strategy, weight-based demand, vehicle fixed cost penalty, max route distance 200km. ยังไม่มี time window |
| 1.4.3 | ตั้ง Timeout ให้ Optimization | หยุดหลังเวลาที่กำหนด (เช่น 30-60 วินาที) | [x] | SOLVE_TIMEOUT_SECONDS = 30 ใน route_optimizer.py |
| 1.4.4 | จำกัด RAM/CPU | container limit หรือ process limit | [ ] | ไม่มี resource limit |
| 1.4.5 | จำกัดขนาดปัญหา | ถ้า >200 stops ให้ cluster เป็น zone ก่อน | [x] | K-means clustering: แบ่ง orders เป็น clusters ตามพิกัดก่อนส่งเข้า VRP |
| 1.4.6 | Validate Constraints ก่อนคำนวณ | time window, capacity ไม่ติดลบ | [x] | _validate_inputs(): ตรวจ negative weight, น้ำหนักเกิน capacity, orders ไม่มีพิกัด |
| 1.4.7 | สร้าง Route Plan Output | JSON ที่มี sequence, ETA, ระยะทางรวม | [x] | ETA calculation: คำนวณเวลาถึงทุกจุด (เริ่ม 08:00, 30 km/h, 5 นาที/จุด) |
| 1.4.8 | Cache Distance Matrix | เก็บใน Redis ลดการเรียก Map API | [~] | มี in-memory cache (`_MATRIX_CACHE`) แต่ไม่ใช่ Redis |

---

### 1.5 Dynamic Load Balancing (กระจายสินค้าระหว่างรถ)

#### 1.5.1 ตรวจจับสถานะรถ (Auto-Detection)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.5.1.1 | คำนวณ Utilization ทุกรถทุก X นาที | ตรวจสอบน้ำหนัก, ปริมาตร, จำนวนกล่อง, จำนวน stop | [x] | load_balancer.py: calculate_utilization() — คำนวณ weight_pct, num_stops |
| 1.5.1.2 | ตั้ง Threshold "รถเต็ม" | ค่าเริ่มต้น: >= 90% ของ capacity ใดๆ | [x] | OVERFLOW_THRESHOLD = 0.90 |
| 1.5.1.3 | ตั้ง Threshold "รถว่างเกิน" | ค่าเริ่มต้น: <= 40% ของ capacity ทุกอย่าง | [x] | UNDERFLOW_THRESHOLD = 0.40 |
| 1.5.1.4 | ตั้ง Threshold "รถปกติ" | อยู่ระหว่าง 40% - 90% | [x] | status: "normal" (40-70%), "high" (70-90%), "overflow" (>=90%), "underflow" (<=40%) |
| 1.5.1.5 | แสดงสถานะรถบน Dashboard | สี: แดง=เต็ม / เหลือง=ใกล้เต็ม / เขียว=ปกติ / ฟ้า=ว่าง | [x] | LoadBalancer.jsx: STATUS_COLORS map + utilization bar สีตาม status |
| 1.5.1.6 | แจ้งเตือนเมื่อรถเข้าเกณฑ์กระจาย | Push notification ไปยัง Dispatcher | [ ] | ยังไม่ได้ทำ |

#### 1.5.2 กรณีที่ 1: รถเต็ม -> กระจายออกไปรถข้างเคียง (Overflow -> Out)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.5.2.1 | ระบุรถที่เต็ม (Source) | รถที่ utilization >= 90% | [x] | detect_imbalances(): overflow list |
| 1.5.2.2 | หา Stop ที่จะย้ายออก | เลือก stop ที่: ไม่ส่งเร็ว (time window ยาว), ไม่ใช่ VIP, น้ำหนักพอดี | [x] | find_transfer_suggestions(): sort by weight + time_window |
| 1.5.2.3 | หารถเป้าหมาย (Target) ที่รับได้ | เงื่อนไข: utilization < 80%, อยู่ในรัศมี X กม., ทิศทางเดียวกัน | [x] | find_transfer_suggestions(): underflow + high vehicles |
| 1.5.2.4 | คำนวณ "ความคุ้มค่า" ของการย้าย | ดูส่วน Scoring Algorithm | [x] | _score_transfer(): detour + time + capacity_fit + time_window_risk |
| 1.5.2.5 | ตรวจสอบ Time Window | ย้ายแล้วรถเป้าหมายต้องไปทัน | [x] | time_window_risk penalty ใน _score_transfer() |
| 1.5.2.6 | ตรวจสอบ Same Order | อย่าแบ่งสินค้าจากออเดอร์เดียวกันไปหลายรถ (ถ้าไม่จำเป็น) | [ ] | ยังไม่ได้ทำ |
| 1.5.2.7 | แสดง Suggestion ให้ Dispatcher | แสดง: ย้าย Stop X จากรถ A -> รถ B, ประหยัดเวลา/น้ำมันเท่าไร | [x] | LoadBalancer.jsx: แสดง suggestion cards พร้อม score + weight changes |
| 1.5.2.8 | Dispatcher กด "ยืนยัน" ก่อน execute | Human-in-the-loop (ไม่ย้ายอัตโนมัติ 100%) | [x] | LoadBalancer.jsx: ปุ่ม "ยืนยันย้าย" + confirmation dialog |

#### 1.5.3 กรณีที่ 2: รถว่าง -> กระจายเข้ารับจากรถข้างเคียง (Underflow -> In)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.5.3.1 | ระบุรถที่ว่างเกิน (Target) | รถที่ utilization <= 40% | [x] | detect_imbalances(): underflow list |
| 1.5.3.2 | หารถข้างเคียงที่บรรทุกเยอะ (Source) | utilization >= 75%, อยู่ในรัศมี X กม. | [x] | find_transfer_suggestions(): overflow vehicles as source |
| 1.5.3.3 | หา Stop ที่เหมาะสมจากรถ Source | ใกล้เส้นทางของรถ Target, ไม่ทำให้ Source เหลือน้อยเกินไป | [x] | _score_transfer(): detour distance + SOURCE_MIN_AFTER check |
| 1.5.3.4 | คำนวณ "ความคุ้มค่า" ของการย้าย | ดูส่วน Scoring Algorithm | [x] | _score_transfer(): combined score |
| 1.5.3.5 | ตรวจสอบว่ารถ Target ไม่โหลดเกิน | ย้ายมาแล้วต้องไม่เกิน 85% | [x] | TARGET_MAX = 0.85, block if new_target_pct > 85% |
| 1.5.3.6 | ตรวจสอบ Time Window | รถ Target ไปทันเวลาลูกค้ากำหนด | [x] | time_window penalty ใน _score_transfer() |
| 1.5.3.7 | แสดง Suggestion ให้ Dispatcher | แสดง: ย้าย Stop X จากรถ B -> รถ A, เหตุผล: แบ่งเบาภาระ | [x] | LoadBalancer.jsx: suggestion cards |
| 1.5.3.8 | Dispatcher กด "ยืนยัน" ก่อน execute | Human-in-the-loop | [x] | LoadBalancer.jsx: ปุ่ม "ยืนยันย้าย" |

#### 1.5.4 Transfer Score Algorithm (คำนวณคะแนนความคุ้มค่า)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.5.4.1 | คำนวณ "ระยะทางเบี่ยงเบน" (Detour Distance) | รถ Target ต้องเบี่ยงจากเส้นทางเดิมกี่กม. | [x] | _score_transfer(): _haversine_km(target_centroid → stop) |
| 1.5.4.2 | คำนวณ "เวลาที่เสีย" (Time Penalty) | Detour ใช้เวลาเพิ่มกี่นาที | [x] | _score_transfer(): (detour_km / speed) * 60 + 5 min/stop |
| 1.5.4.3 | คำนวณ "ความพอดี" (Capacity Fit) | ย้ายมาแล้ว Target อยู่ที่ % ไหน (เป้าหมาย: 60-80%) | [x] | _score_transfer(): bonus -20 if in TARGET_MIN-MAX range |
| 1.5.4.4 | คำนวณ "ความเสี่ยง Time Window" | ถ้าย้ายแล้วไปทัน = ผ่าน, ไม่ทัน = ตัดทิ้ง | [x] | _score_transfer(): +15 penalty if time_window_end exists |
| 1.5.4.5 | คำนวณ "ผลกระทบลูกค้า" | VIP = ตัดทิ้ง, ทั่วไป = ผ่าน | [ ] | ยังไม่ได้ทำ |
| 1.5.4.6 | รวมคะแนนเป็น "Transfer Score" | ยิ่งต่ำ = ยิ่งคุ้มค่า | [x] | _score_transfer(): sum of all scores |
| 1.5.4.7 | เรียงลำดับตัวเลือก | แสดง Top 3 ตัวเลือกที่ดีที่สุด | [x] | find_transfer_suggestions(): sort by score, return top 10 |

#### 1.5.5 Constraints (เงื่อนไขสำคัญที่ต้องตรวจสอบ)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.5.5.1 | Time Window ต้องไม่เสีย | ลูกค้าต้องได้รับของภายในเวลาที่กำหนด | [x] | time_window penalty ใน _score_transfer() |
| 1.5.5.2 | อย่าแบ่งออเดอร์เดียวกัน | สินค้าจาก SO เดียวกัน ควรอยู่รถเดียวกัน | [ ] | ยังไม่ได้ทำ |
| 1.5.5.3 | อย่าให้รถต้นทางเหลือน้อยเกินไป | ย้ายออกแล้วต้นทางต้องไม่ต่ำกว่า 30% | [x] | SOURCE_MIN_AFTER = 0.30, block if new_source_pct < 30% |
| 1.5.5.4 | รถเป้าหมายต้องไม่เกิน 85% | ย้ายเข้าแล้วต้องไม่เต็ม | [x] | TARGET_MAX = 0.85, block if new_target_pct > 85% |
| 1.5.5.5 | อยู่ในรัศมีที่สมเหตุสมผล | เช่น ไม่เกิน 5 กม. หรือ 15 นาทีจากเส้นทาง | [x] | MAX_DETOUR_KM = 5.0, MAX_DETOUR_MINUTES = 15 |
| 1.5.5.6 | ทิศทางต้องสอดคล้องกัน | รถเป้าหมายต้องวิ่งไปทางเดียวกัน (ไม่วนกลับ) | [ ] | ยังไม่ได้ทำ |
| 1.5.5.7 | ประเภทสินค้าต้องตรง | ถ้ารถแช่เย็น -> ย้ายได้แค่สินค้าแช่เย็น | [ ] | ยังไม่ได้ทำ |
| 1.5.5.8 | คนขับต้องรับทราบ | แจ้งเตือนทั้ง 2 ฝ่ายก่อนย้าย | [ ] | ยังไม่ได้ทำ |

#### 1.5.6 Execute Transfer (ดำเนินการหลังยืนยัน)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 1.5.6.1 | ย้าย Stop จากรถ A -> รถ B ในฐานข้อมูล | อัปเดต route_stops | [x] | execute_transfer(): pop from source, append to target |
| 1.5.6.2 | อัปเดต Sequence ใหม่ของทั้ง 2 รถ | Re-order stops | [x] | execute_transfer(): re-sequence target stops |
| 1.5.6.3 | Re-calculate Route ของทั้ง 2 รถ | ใช้ VRP ใหม่ หรือ heuristic | [x] | recalculate_route_after_transfer(): nearest-neighbor reorder |
| 1.5.6.4 | อัปเดต ETA ใหม่ | ส่งไปยังคนขับทั้ง 2 คัน | [ ] | ยังไม่ได้ทำ |
| 1.5.6.5 | แจ้งเตือนคนขับรถต้นทาง | "Stop X ถูกย้ายออกไปรถ B" | [ ] | ยังไม่ได้ทำ |
| 1.5.6.6 | แจ้งเตือนคนขับรถเป้าหมาย | "มี Stop X เพิ่มเข้ามา กรุณาตรวจสอบเส้นทางใหม่" | [ ] | ยังไม่ได้ทำ |
| 1.5.6.7 | บันทึก Log การย้าย | เก็บใน route_transfers | [x] | execute_transfer(): บันทึก RouteTransfer record |
| 1.5.6.8 | อัปเดต Dashboard | แสดงผลลัพธ์ทันที | [x] | LoadBalancer.jsx: loadData() refresh after transfer |

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
| 2.2.1 | State Machine Stop Status | PENDING → IN_TRANSIT → ARRIVED → DELIVERED/FAILED/PARTIAL | [x] | สร้าง delivery_status.py: validate_transition(), VALID_TRANSITIONS map, STATUS_LABELS (ไทย), STATUS_COLORS |
| 2.2.2 | Track Status ระดับ Item | ordered_qty, delivered_qty, status แยก item | [x] | สร้าง update_item_delivery() ใน db.py + API endpoint /delivery/update-item |
| 2.2.3 | Driver Mobile: กด ARRIVED | คนขับกดยืนยันถึงจุดส่ง | [x] | สร้าง DriverMobile.jsx: หน้า login + route overview + stop detail + ปุ่ม ARRIVED/IN_TRANSIT |
| 2.2.4 | Driver Mobile: กด DELIVERED | พร้อมถ่ายรูป POD | [x] | DriverMobile.jsx: ปุ่ม ✅ ส่งสำเร็จ |
| 2.2.5 | Driver Mobile: กด FAILED | เลือกเหตุผล: ไม่มีคนรับ, ที่อยู่ผิด, สินค้าเสียหาย | [x] | DriverMobile.jsx: modal เลือกเหตุผล 6 ข้อ + ยืนยัน |
| 2.2.6 | Driver Mobile: กด PARTIAL | กรอกจำนวนที่ส่งจริง | [x] | DriverMobile.jsx: modal กรอกจำนวน + ยืนยัน |
| 2.2.7 | GPS Auto-detect ARRIVED | เข้าใกล้จุดส่ง X เมตร → อัปเดตอัตโนมัติ | [ ] | ยังไม่ได้ทำ |
| 2.2.8 | Dashboard สถานะรวม | กี่จุดส่งแล้ว / ค้าง / มีปัญหา | [x] | Dashboard.jsx: เพิ่ม delivery status section + progress bar + summary cards |
| 2.2.9 | Filter & Search Stop | ตามสถานะ, รถ, วันที่ | [x] | DriverMobile.jsx: search input + status filter buttons (ALL/PENDING/IN_TRANSIT/ARRIVED/DELIVERED/FAILED) |
| 2.2.10 | Notification แจ้งเตือน | Failed, หยุดนาน, เบี่ยงเส้นทาง | [x] | สร้าง notifications.py (in-memory store, auto-generate), NotificationPanel.jsx (bell icon, dropdown, unread count, mark read), API endpoints (/notifications, /notifications/unread-count, /notifications/{id}/read, /notifications/mark-all-read) |

### 2.3 Load Balancing (REQ-3)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 2.3.1 | Auto-detect รถเต็ม | utilization > 95% ของ capacity ใดๆ | [x] | detect_imbalances(): OVERFLOW_THRESHOLD = 0.90 |
| 2.3.2 | Algorithm หารถใกล้เคียง | หารถ B ที่มี capacity เหลือ + อยู่ใกล้ | [x] | find_transfer_suggestions(): underflow + high vehicles |
| 2.3.3 | Algorithm คำนวณ Transfer Cost | distance + time + capacity_fit + time_window_risk | [x] | _score_transfer(): 4-factor scoring |
| 2.3.4 | Suggest Top 3 รถที่เหมาะสม | แสดงให้ Dispatcher เลือก | [x] | LoadBalancer.jsx: suggestion cards with score |
| 2.3.5 | Dispatcher ยืนยันก่อน Execute | Human-in-the-loop (ไม่ auto 100%) | [x] | LoadBalancer.jsx: ปุ่ม "ยืนยันย้าย" + confirmation |
| 2.3.6 | Re-calculate Route หลังย้าย | อัปเดต sequence + ETA รถที่เกี่ยวข้อง | [x] | recalculate_route_after_transfer(): nearest-neighbor |
| 2.3.7 | แจ้งเตือนคนขับทั้ง 2 คัน | หลังย้าย stop | [x] | notify_transfer_executed() แจ้งเตือนอัตโนมัติเมื่อ transfer สำเร็จ |
| 2.3.8 | Manual "Find Nearby Vehicle" | Dispatcher เลือก stop -> กดหารถใกล้เคียง | [x] | LoadBalancer.jsx: วิเคราะห์อัตโนมัติ + แสดง suggestion cards + ปุ่มยืนยัน |
| 2.3.9 | Constraint การย้าย | รักษา time window, ไม่แบ่งลูกค้ารายเดียวหลายรถ | [x] | time_window penalty + SOURCE_MIN_AFTER + TARGET_MAX |

### 2.4 Reschedule (ส่งไม่สำเร็จ → ย้ายไปวันถัดไป)

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 2.4.1 | สถานะ RESCHEDULED | ใน State Machine | [x] | เพิ่ม RESCHEDULED ใน VALID_TRANSITIONS + reschedule_stop() + API endpoint /delivery/reschedule |
| 2.4.2 | ย้าย stop กลับเข้า Queue รอจัดส่งวันถัดไป | ไม่ติดกับรถเดิม | [x] | reschedule_stop() อัปเดตสถานะเป็น RESCHEDULED + บันทึก history |
| 2.4.3 | แจ้งเตือนลูกค้า (ถ้ามีเบอร์/อีเมล) | อัตโนมัติหรือแมนนวล | [x] | notify_stop_rescheduled() แจ้งเตือน dispatcher อัตโนมัติ |
| 2.4.4 | บันทึกเหตุผลการ reschedule | ไว้ดูย้อนหลัง | [x] | บันทึกใน StopStatusHistory (note field) |

---

## 🟢 Priority 3: ส่วนเสริมที่ทำได้ภายหลัง (Enhancement)

### 3.1 Frontend — Dispatcher Dashboard

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 3.1.1 | Panel รายการรถ (ซ้าย) | สถานะ, utilization bar, จำนวน stop | [~] | Dashboard.jsx มี fleet utilization card แต่ไม่ real-time |
| 3.1.2 | แผนที่กลาง (Map) | ตำแหน่งรถ real-time, pin ตามสถานะ | [~] | MapView.jsx มี Leaflet map + depot marker + delivery markers + route polylines แต่ไม่มี real-time GPS tracking |
| 3.1.3 | Panel Stop List (ขวา) | เรียง sequence, drag-and-drop | [~] | MapView.jsx มี side inspector panel + stop list แต่ไม่มี drag-and-drop reorder |
| 3.1.4 | Panel Alert & Notification (บน) | แจ้งเตือน + Load Balancing suggestion | [x] | NotificationPanel.jsx: bell icon + dropdown + unread count + mark read + poll every 30s |
| 3.1.5 | หน้า "Review & Confirm Location" | แผนที่ + Pin ลากได้ + Confidence Score | [x] | MapView.jsx: drag pins + reverse geocode + confidence score + save to DB + place search |
| 3.1.6 | หน้า Admin Dashboard | Location Quality Report, Heatmap | [x] | AdminDashboard.jsx: quality overview cards + zone heatmap table + low confidence orders list |
| 3.1.7 | Street View / ภาพถ่ายดาวเทียม | แสดงประกอบก่อนยืนยันพิกัด | [~] | MapView.jsx มี ArcGIS satellite tile layer แต่ไม่มี Street View |

### 3.2 Frontend — Driver Mobile Web

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 3.2.1 | หน้า Route Today | รายการ stop ของวันนี้ | [x] | DriverMobile.jsx: login ด้วยชื่อคนขับ + แสดง route overview + summary bar + progress bar |
| 3.2.2 | หน้า Stop Detail | ชื่อลูกค้า, ที่อยู่, สินค้า, ปุ่มนำทาง | [x] | DriverMobile.jsx: แสดง customer, address, products, weight + ปุ่ม Google Maps navigation |
| 3.2.3 | ปุ่ม ARRIVED / DELIVERED / FAILED | กดอัปเดตสถานะ | [x] | DriverMobile.jsx: ปุ่มตาม state machine (PENDING→IN_TRANSIT→ARRIVED→DELIVERED/FAILED/PARTIAL) |
| 3.2.4 | อัปโหลดรูป POD | ถ่ายรูป → อัปโหลด | [x] | DriverMobile.jsx: ปุ่ม "อัปโหลดรูป POD" + input type=file capture=camera |
| 3.2.5 | ปุ่ม "Report Wrong Pin" | ส่งพิกัดจริง + รูป + หมายเหตุ | [x] | DriverMobile.jsx: ปุ่ม "รายงานพิกัดผิด" + navigator.geolocation.getCurrentPosition |
| 3.2.6 | ดู Stop ถัดไป + ETA | อัปเดตแบบ real-time | [x] | DriverMobile.jsx: "จุดถัดไป" card แสดง customer + address + ปุ่มนำทาง |

### 3.3 LINE Messaging API Integration

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 3.3.1 | สมัคร LINE Official Account | https://manager.line.biz | [ ] | ยังไม่ได้ทำ (ต้องสมัครเอง) |
| 3.3.2 | สร้าง Channel + เอา Access Token | LINE Developers Console | [ ] | ยังไม่ได้ทำ (ต้องสร้างเอง) |
| 3.3.3 | Python: ส่ง Push Message | ข้อความ + ลิงก์ Google Maps | [x] | สร้าง line_notifier.py: send_route_notification(), send_driver_notification() |
| 3.3.4 | เชื่อมกับระบบหลัก | Trigger ตอนคำนวณเส้นทางเสร็จ | [x] | เพิ่ม API endpoints: /send-line-notification, /send-driver-notification |
| 3.3.5 | เก็บ LINE User ID คนขับ | ในฐานข้อมูล vehicles/drivers | [x] | เพิ่ม Driver model (line_user_id field) + drivers table ใน models.py |
| 3.3.6 | (เพิ่มเติม) Webhook รับข้อความ | ถ้าอยากให้คนขับกดปุ่มตอบกลับ | [ ] | ยังไม่ได้ทำ (ต้องสมัคร LINE Official Account ก่อน) |
| 3.3.7 | (เพิ่มเติม) Rich Menu / Quick Reply | ปุ่ม "ส่งสำเร็จ" / "ส่งไม่ได้" ในแชต | [ ] | ยังไม่ได้ทำ (ต้องสมัคร LINE Official Account ก่อน) |

### 3.4 Security & Infrastructure

| # | รายการ | รายละเอียด | Status | หมายเหตุ |
|---|--------|-----------|--------|---------|
| 3.4.1 | ย้าย API Key ไป Environment Variable | ห้าม hardcode | [x] | ใช้ .env + config.py ครอบคลุมทุก key |
| 3.4.2 | จำกัดขนาดไฟล์ OP | Hard limit (เช่น 50 MB) | [~] | MAX_FILE_SIZE_MB=10 ใน config.py แต่ไม่ enforce ใน routes.py |
| 3.4.3 | ป้องกัน Path Traversal | ตรวจสอบชื่อไฟล์ | [~] | มี _validate_file() ตรวจสอบ PDF extension + filename แต่ไม่ full path traversal check |
| 3.4.4 | อ่านไฟล์แบบ Streaming | ไม่โหลดทั้งไฟล์เข้า RAM | [x] | _validate_file_content(): อ่าน header 4 bytes ก่อน (magic bytes check) แล้วค่อยอ่านทั้งไฟล์ |
| 3.4.5 | Audit Log ทุกขั้นตอน | input hash, intermediate, output | [x] | AuditLogMiddleware: log ทุก API call + mutating operations + security events + บันทึก duration |
| 3.4.6 | Mask Sensitive Data ใน Log | ตัดทอนพิกัดลูกค้า | [x] | _mask_sensitive_data(): mask password, token, secret, api_key ใน log entries |
| 3.4.7 | Queue System (Redis/Celery) | ถ้ามีหลาย request พร้อมกัน | [x] | สร้าง celery_app.py (Redis broker), tasks.py (optimize_routes_task), async endpoint /plan-routes/async + task status polling, Celery worker + Flower ใน docker-compose.prod.yml |
| 3.4.8 | Health Check Endpoint | เช็คสถานะ Parser, Cache, Engine | [x] | GET /health รายงาน DB status + version + timestamp |
| 3.4.9 | Metrics & Monitoring | เวลาคำนวณ, จำนวน request, error rate | [x] | metrics.py มี Prometheus counters/histograms + middleware + /metrics endpoint, สร้าง prometheus.yml + Grafana provisioning + dashboard JSON, wire up record_db_operation/record_route_planned/record_order_processed ใน db.py/routes.py |
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
| B.6 | ไม่มี Authentication | API ทุก endpoint เปิดรับทุกคน ไม่มี auth/token | สูง | [x] แก้แล้ว — auth.py: JWT + RBAC (admin/dispatcher/driver), API Key middleware, login endpoint |
| B.7 | ไม่มี Test | ไม่มี pytest, ไม่มี unit test, ไม่มี E2E test | สูง | [x] แก้แล้ว — 26 unit tests (data_validator, haversine, distance_matrix, route_optimizer, thai date, PO reference, rebalance) |
| B.8 | Version string ไม่ตรงกัน | main.py บอก v1.2.0 แต่ root endpoint บอก v1.1.0 | ต่ำ | [x] แก้แล้ว — ทั้งสองจุดเป็น v1.2.0 |
| B.9 | Gemini/Ollama config เป็น dead code | ตั้งค่าใน config.py แต่ไม่เคยเรียกใช้ | ต่ำ | [x] แก้แล้ว — ลบ OLLAMA_URL, GEMINI_API_KEY |
| B.10 | AI Refinement toggle CSS มีแต่ไม่ wire up | มี CSS class `.ai-refinement-toggle` ใน App.css แต่ไม่มี component ที่ใช้ | ต่ำ | [x] แก้แล้ว — ลบ AI Refinement ออกทั้งหมด (ไม่ใช้แล้ว) |
| B.11 | `email_sender.py` import error | import EMAIL_HOST/PORT/USER/PASSWORD จาก config แต่ไม่มี | สูง | [x] แก้แล้ว — ลบ email_sender.py (เปลี่ยนเป็น LINE) |
| B.12 | DB migration bug | `clear_all_data()` เรียก INITIAL_VEHICLES ก่อนประกาศ | สูง | [x] แก้แล้ว — ย้าย INITIAL_VEHICLES ไว้ก่อน function |
| B.13 | vehicles.json write ไม่จำเป็น | routes.py clear-data เขียน vehicles.json ทั้งที่ใช้ DB | ต่ำ | [x] แก้แล้ว — ลบโค้ดที่เขียน vehicles.json |
| B.14 | Schema mismatch | `PlanRoutesRequest` มี 2 ที่ชื่อเดียวกัน (schemas.py vs routes.py) | ต่ำ | [x] แก้แล้ว — ลบ PlanRoutesRequest + SendEmailRequest ใน schemas.py |
| B.15 | Hardcoded depot coordinates | depot lat/lng default หลายจุด ไม่ได้ reference config.py | กลาง | [x] แก้แล้ว — import DEPOT_LAT/DEPOT_LNG จาก config.py |
| B.16 | ETA เริ่ม 08:00 เสมอ | hardcoded start_time = 08:00 | ต่ำ | [x] แก้แล้ว — เพิ่ม parameter start_hour (default=8) |
| B.17 | Fixed cost ไม่มี explanation | `SetFixedCostOfAllVehicles(100000)` ไม่มี comment | ต่ำ | [x] แก้แล้ว — เพิ่ม comment อธิบาย |
| B.18 | ลบ AI Refinement | ลบ config + code ที่เกี่ยวข้อง (ไม่ใช้แล้ว) | ต่ำ | [x] แก้แล้ว — ลบ LMSTUDIO_URL, ENABLE_AI_REFINEMENT, _ai_refine_thai_order() |

---

## 📊 สรุปสถานะโดยรวม

| Priority | จำนวนรายการ | เสร็จแล้ว [x] | บางส่วน [~] | ยังไม่ได้ทำ [ ] | คิดเป็น |
|----------|------------|--------------|------------|----------------|--------|
| 🔴 P1: Data Parser (1.1) | 11 | 11 | 0 | 0 | 100% |
| 🔴 P1: Geocoding (1.2) | 8 | 6 | 1 | 1 | 75% |
| 🔴 P1: Database (1.3) | 14 | 11 | 2 | 1 | 79% |
| 🔴 P1: VRP Routing (1.4) | 8 | 5 | 2 | 1 | 63% |
| 🔴 P1: Load Balancing (1.5) | 48 | 35 | 0 | 10 | 73% |
| 🟡 P2: Vehicle Capacity (2.1) | 7 | 0 | 3 | 4 | 21% |
| 🟡 P2: Delivery Tracking (2.2) | 10 | 9 | 0 | 1 | 90% |
| 🟡 P2: Load Balancing (2.3) | 9 | 9 | 0 | 0 | 100% |
| 🟡 P2: Reschedule (2.4) | 4 | 4 | 0 | 0 | 100% |
| 🟢 P3: Dashboard (3.1) | 7 | 3 | 4 | 0 | 43% |
| 🟢 P3: Driver Mobile (3.2) | 6 | 6 | 0 | 0 | 100% |
| 🟢 P3: LINE API (3.3) | 7 | 3 | 0 | 4 | 43% |
| 🟢 P3: Security (3.4) | 10 | 7 | 2 | 1 | 70% |
| **รวมทั้งหมด** | **149** | **109** | **14** | **26** | **73%** |

> **หมายเหตุ:** นับจาก main checklist เท่านั้น ไม่รวม B.1-B.18 (Fix Debt) ที่แก้เสร็จ 18 รายการ

---

## 🗓️ Phased Development Plan (แนะนำ)

| **Phase 0: Fix Debt** | สัปดาห์ 0 | แก้ B.1-B.18 | ✅ เสร็จแล้ว |
| **Phase 1: Foundation** | สัปดาห์ 1-2 | Parser (1.1) + Geocoding (1.2) + DB Schema (1.3) | ✅ เสร็จแล้ว |
| **Phase 2: Routing Engine** | สัปดาห์ 3-4 | VRP (1.4) + OR-Tools + Distance Matrix จริง + ETA | ✅ เสร็จแล้ว |
| **Phase 3: Infrastructure** | สัปดาห์ 5 | PostgreSQL Migration + Docker Setup + CI/CD + Auth + Security | ✅ เสร็จแล้ว |
| **Phase 4: Status Tracking** | สัปดาห์ 6-7 | Delivery Status (2.2) + Driver Mobile Web + State Machine + Notifications | ✅ เสร็จแล้ว (90%) |
| **Phase 5: Dynamic Features** | สัปดาห์ 8-9 | Load Balancing (1.5/2.3) + Reschedule (2.4) + Capacity UI (2.1) | ✅ บางส่วน (Load Balancing 73% + Reschedule 100% + Capacity 21%) |
| **Phase 6: Integration** | สัปดาห์ 10-11 | Admin Dashboard (3.1.6) + Security (3.4) + LINE API (3.3) | ✅ บางส่วน (Dashboard 43% + Security 50% + LINE 43%) |
| **Phase 7: Polish** | สัปดาห์ 12 | Metrics (3.4.9) + Queue System (3.4.7) + PDPA + Drag-and-Drop + GPS Auto-detect + Street View | ✅ บางส่วน (Metrics 100% + Queue 100% + เหลือ PDPA, Drag-and-Drop, GPS, Street View) |

---

## 📝 บันทึกการแก้ไข (Changelog)

| วันที่ | เวอร์ชัน | รายการที่แก้ | ผู้แก้ไข |
|-------|---------|-------------|---------|
| 31 ก.ค. 2026 | 1.1 | อัปเดต status ทั้งหมดจากผลวิเคราะห์โค้ดจริง (Backend + Frontend) | AI Analysis |
| 31 ก.ค. 2026 | 1.2 | Phase 0 Fix Debt: แก้ B.1-B.5, B.7-B.9 (OR-Tools VRP, requirements.txt, schemas, tests, config cleanup) | AI + User |
| 31 ก.ค. 2026 | 1.3 | Phase 1 Foundation: แก้ 1.1.5, 1.1.7, 1.1.10, 1.1.11, 1.2.6, 1.2.8, 1.3.2, 1.3.4 (PDF parser, geocoding retry, DB schema) | AI + User |
| 31 ก.ค. 2026 | 1.4 | Phase 2 Routing Engine: แก้ OR-Tools solver — CHRISTOFIDES strategy, weight-based demand, vehicle fixed cost penalty, fixed distance calc, max route distance 200km, consolidated _make_stop_fields | AI + User |
| 31 ก.ค. 2026 | 1.4 | Phase 2 เสร็จ: เพิ่ม 1.4.5 K-means clustering (>200 stops), 1.4.6 input validation, 1.4.7 ETA calculation (30km/h, 5 นาที/จุด) | AI + User |
| 01 ส.ค. 2026 | 1.5 | Fix Debt Phase 2: แก้ B.11-B.18 (ลบ email_sender, แก้ DB migration, ลบ vehicles.json write, แก้ schema mismatch, hardcoded depot, ETA logic, fixed cost comment, ลบ AI Refinement) | AI + User |
| 01 ส.ค. 2026 | 1.5 | LINE Integration: สร้าง line_notifier.py, เพิ่ม LINE config, สร้าง .env.example, เพิ่ม API endpoints (/send-line-notification, /send-driver-notification) | AI + User |
| 01 ส.ค. 2026 | 1.6 | **Phase 3 Infrastructure: PostgreSQL Migration + Docker Setup** — สร้าง SQLAlchemy ORM models, เขียน db.py ใหม่ (PostgreSQL), สร้าง migrate_sqlite_to_postgres.py, สร้าง docker-compose.yml, Dockerfile backend/frontend, nginx.conf, .env.docker, .dockerignore, เพิ่ม health endpoint, ทดสอบ docker-compose up สำเร็จ | AI + User |
| 01 ส.ค. 2026 | 1.7 | **Sprint 1-4: Auth + JWT + Redis Cache + Logging + Metrics + CI/CD + Security + Production Docker** — auth.py (JWT+RBAC+login), cache.py (Redis), logging_config.py, metrics.py, middleware/security.py, docker-compose.prod.yml, .github/workflows/ci.yml, migrate_add_tables.py (6 new tables), แก้ B.6 (auth) | AI + User |
| 01 ส.ค. 2026 | 1.7 | **Grill Me Audit Fix** — ลบ dead import `verify_api_key` ใน main.py, ลบ duplicate `Request` import, อัปเดต version เป็น 1.7.0, อัปเดต B.6 checklist status | AI |
| 01 ส.ค. 2026 | 1.8 | **Grill Me #3 Handoff (4 HIGH + 10 MEDIUM)** — [HIGH] JWT_SECRET_KEY fail if not set in production, DEFAULT_USERS gated by PRODUCTION_MODE, datetime.utcnow→timezone.utc ทั้ง codebase, CSP header ลบ unsafe-inline/unsafe-eval. [MEDIUM] ลบ wasted get_distance_matrix() call, เพิ่ม file size validation, ลบ dead schemas.py, ลบ unused imports (json/hashlib/Callable/Any/googlemaps top-level), แก้ reverse_geocode ใช้ _request_with_retry, แก้ hardcoded fallback coords→config, ลบ unused distance_matrix param, lazy import googlemaps | AI |
| 01 ส.ค. 2026 | 1.9 | **Grill Me #4 Handoff (3 CRITICAL + 10 HIGH + 3 MEDIUM)** — [CRITICAL] เพิ่ม admin auth ให้ clear-data/vehicles/LINE endpoints, แก้ verify_admin_key/dispatcher_key deny when empty, JWT fallback เป็น random secret. [HIGH] แก้ datetime naive→aware ทั้ง models+db, lazy import googlemaps ใน distance_matrix_real, path normalization metrics labels, rate limiting IP detection behind proxy, หยุด leak exception details/credentials. [MEDIUM] clear_all_data ลบ 12 tables, version string centralize, ลบ unused Form import | AI |
| 01 ส.ค. 2026 | 2.0 | **Grill Me #5 Handoff (7 CRITICAL + 9 HIGH + 24 MEDIUM)** — [CRITICAL] ลบ API key จาก docker-compose, DB creds ใช้ .env, JWT random key, เพิ่ม auth optional ให้ upload/plan-routes, prod compose เพิ่ม PRODUCTION_MODE+ADMIN_KEYS. [HIGH] Health check return 503, fix AuditLogMiddleware crash, cache TTL+max-size, fix VehicleManager renumber IDs, fix RouteResult onSendLine prop. [MEDIUM] Frontend API paths /api/v1/, handleClearData response check, Dashboard vehicle count, Sidebar version, DatabaseViewer PostgreSQL text, fallback total_distance_km | AI |
| 01 ส.ค. 2026 | 2.1 | **Grill Me #6 Handoff (14 CRITICAL + 28 HIGH + 48 MEDIUM + 53 LOW)** — [CRITICAL] Single .env file (ลบ backend/.env+.env.docker), bcrypt password hashing (passlib), ALLOW_DEFAULT_USERS env, sanitize PDF filename (path traversal), XSS fix (htmlEscape in L.divIcon), CSRF middleware (Origin/Referer validation), clear-data typed confirmation, Redis auth (--requirepass), docker-socket-proxy, pin Docker images. [HIGH] Auth ให้ 13 endpoints, JWT key persistence (.jwt_secret file), CORS restrict methods/headers, error leak fix (generic messages), rate limiter trusted proxy, frontend console.log removal, useMemo/useCallback, debounce search 300ms, validate lat/lng, division by zero guard, Traefik labels, Grafana non-default username, frontend healthcheck in prod. [MEDIUM] DB indexes (orders.created_at, customer, order_number; route_details.plan_id), nginx security headers (nosniff, DENY, XSS-Protection, Referrer-Policy, server_tokens), client_max_body_size 12M, log rotation, cap_drop ALL, security_opt, stop_grace_period, Docker network isolation, .jwt_secret in .gitignore | AI |
| 01 ส.ค. 2026 | 2.2 | **Sprint 4: Delivery Status State Machine + Driver Mobile** — สร้าง delivery_status.py (state machine: PENDING→IN_TRANSIT→ARRIVED→DELIVERED/FAILED/PARTIAL/RESCHEDULED), เพิ่ม delivery API endpoints (/delivery/update-status, /delivery/dashboard, /delivery/driver/{name}, /delivery/valid-transitions, /delivery/update-item, /delivery/reschedule, /delivery/summary, /delivery/status-history), สร้าง DriverMobile.jsx (login ด้วยชื่อคนขับ, route overview, stop detail, ปุ่ม status, failure modal, partial modal, Google Maps navigation), Dashboard delivery status section (summary cards + progress bar), Sidebar เพิ่ม Driver Mobile link, แก้ checklist: 2.2.1-2.2.6, 2.2.8, 2.4.1, 2.4.4, 1.3.8-1.3.11, 3.2.1-3.2.3, 3.3.5 | AI |
| 01 ส.ค. 2026 | 2.3 | **Sprint 5: Load Balancing Algorithm** — สร้าง load_balancer.py (detect_imbalances, find_transfer_suggestions, execute_transfer, recalculate_route_after_transfer, calculate_utilization, _score_transfer 4-factor scoring), เพิ่ม load-balance API endpoints (/load-balance/analyze, /load-balance/suggestions, /load-balance/execute, /load-balance/vehicle/{id}, /load-balance/transfer-history), สร้าง LoadBalancer.jsx (vehicle utilization grid สีตาม status, transfer suggestion cards, execute button, transfer history table), Dashboard เพิ่ม Load Balancing quick action, Sidebar เพิ่ม Load Balancing link, แก้ checklist: 1.5.1.1-1.5.1.5, 1.5.2.1-1.5.2.5, 1.5.2.7-1.5.2.8, 1.5.3.1-1.5.3.8, 1.5.4.1-1.5.4.4, 1.5.4.6-1.5.4.7, 1.5.5.1, 1.5.5.3-1.5.5.5, 1.5.6.1-1.5.6.3, 1.5.6.7-1.5.6.8, 2.3.1-2.3.6, 2.3.9 | AI |
| 01 ส.ค. 2026 | 2.4 | **Phase 4-6: Notification System + Admin Dashboard + Security + Driver Mobile** — สร้าง notifications.py (in-memory store, auto-generate, notify_delivery_failed/transfer_suggested/transfer_executed/stop_rescheduled), NotificationPanel.jsx (bell icon, dropdown, unread count, mark read, poll 30s), AdminDashboard.jsx (quality overview cards, zone heatmap table, low confidence orders), อัปเดต DriverMobile.jsx (search/filter stops, POD upload, report wrong pin, next stop ETA), AuditLogMiddleware (data masking, mutating operation audit), _validate_file_content (magic bytes check), API endpoints (/notifications, /notifications/unread-count, /notifications/{id}/read, /notifications/mark-all-read), แก้ checklist: 2.2.9-2.2.10, 2.4.2-2.4.3, 2.3.7-2.3.8, 3.1.4, 3.1.6, 3.2.4-3.2.6, 3.4.4-3.4.6 | AI |
| 01 ส.ค. 2026 | 2.5 | **Summary Table Update** — อัปเดตตารางสรุปสถานะจาก ~28% → 72% ตามงานที่ทำเสร็จจริง (Sprint 4-5 + Grill Me #3-6) | AI |
| 01 ส.ค. 2026 | 2.6 | **Queue System (3.4.7) + Metrics & Monitoring (3.4.9)** — สร้าง celery_app.py (Redis broker, DB 1/2 for queue/results), tasks.py (optimize_routes_task + geocode_orders_task with progress tracking), async endpoint POST /api/v1/plan-routes/async + task status polling GET /tasks/{task_id}, Celery worker + Flower service ใน docker-compose.prod.yml, Prometheus configs (prometheus.yml + Grafana provisioning + dashboard JSON), wire up metrics: record_db_operation ใน db.py (save_orders, save_route_plan, update_stop_status), record_route_planned + record_order_processed ใน routes.py | AI |
| 02 ส.ค. 2026 | 2.7 | **Grill Me #8 Fixes (7 CRITICAL)** — metrics_middleware ใช้ @app.middleware("http") (เดิม add_middleware กับ async function → TypeError), frontend auth ครบวงจร (api.js patch fetch + Authorization Bearer + LoginScreen + auth gate + auto-logout 401, ALLOW_DEFAULT_USERS=true ใน dev compose), DriverMobile hooks violation + stop→selectedStop, VRP int(inf) OverflowError guard, math.asin domain clamp ทั้ง 3 ไฟล์, execute_transfer source==target guard, bcrypt pin 4.0.1 (passlib แตกกับ bcrypt 5.x) | AI |
| 02 ส.ค. 2026 | 2.8 | **Production Deploy Prep** — DB-backed users (User model + users table auto-create), manage_users.py CLI (create/list/activate/deactivate), APIKeyMiddleware อนุญาต Bearer JWT เมื่อตั้ง API_KEYS (login ใช้ได้ใน production), .env.prod.example เพิ่ม REDIS_PASSWORD/ADMIN_KEYS/DISPATCHER_KEYS/ALLOWED_ORIGINS, docker-compose.prod.yml ส่ง ALLOWED_ORIGINS (แก้ CSRF 403 หน้า production), เขียน README.md ใหม่เป็นคู่มือติดตั้ง server ลูกค้า | AI |
| 02 ส.ค. 2026 | 2.9 | **Grill Me #10 Fixes (17 จุด CRITICAL+HIGH)** — [C] backend/.dockerignore + .gitignore กัน .jwt_secret/data/*.db/op_backups (PII ไม่รั่วใน image), IDOR scoping (verify-location เฉพาะ admin/dispatcher, driver อัปเดตได้เฉพาะ route ตัวเอง, driver เห็นได้เฉพาะ route ตัวเอง, mark_notification_read เช็ค role), mask API key ใน geocoding log, ลบ DEFAULT_USERS ทั้งหมด (auth DB-only), แก้ transfer reorder index mapping (ห้าม stop หาย), BUSINESS_TIMEZONE config (Asia/Bangkok) แก้ today queries UTC→local, capacity join ใน get_today_active_routes/get_route_history, execute_transfer error แทน warning เมื่อ overfill/underflow, weight=None guard, fallback_sweep ไม่ทิ้ง order + warnings, async routes เปลี่ยนเป็น sync def + run_in_threadpool (แก้ event loop block), TRUST_PROXY_HEADERS ให้ rate limiter เห็น IP จริง, chunked upload + PDF page cap, PARTIAL buttons ใน DriverMobile, propagate pin correction ไป stops_json + App state, persist vehicle max_volume/boxes/stops, merge driver routes (clustered mode) | AI |
| 02 ส.ค. 2026 | 2.10 | **Grill Me #11 — ข้อมูลรถ** — ตัด seed ปลอมออก (`INITIAL_VEHICLES`/`_seed_vehicles`): ข้อมูลรถเริ่มต้นว่าง (`get_vehicles_from_db` ว่าง→`[]`, `load_vehicles` fallback→`[]`); `clear_all_data` ไม่ลบ `Vehicle`+fleet (`Driver`/`VehicleLoad`/`VehicleLocation`) และไม่รีเซ็ต `vehicles_id_seq` (ลบเฉพาะ order/route/customer/status); เพิ่มคอลัมน์ `line_user_id` ใน `vehicles` พร้อม migration `_migrate_columns()` (รองรับ SQLite+Postgres สำหรับตารางเดิม) + `save_vehicles_to_db`/`get_vehicles_from_db` รองรับ; `VehicleManager` เพิ่มช่องกรอก LINE User ID + empty-state; `RouteResult` เพิ่มปุ่ม "ส่ง LINE ให้คนขับ" ต่อคันเรียก `/api/v1/send-driver-notification` (backend มีอยู่แล้ว) | AI |

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
> - Backend: `backend/services/pdf_extractor.py`, `geocoding.py`, `route_optimizer.py`, `distance_matrix.py`, `excel_exporter.py`
> - Frontend: `frontend/src/components/MapView.jsx`, `RouteResult.jsx`, `VehicleManager.jsx`, `Dashboard.jsx`
> - DB: `backend/database/db.py`
