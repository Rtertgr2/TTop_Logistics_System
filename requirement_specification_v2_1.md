# 📋 Requirement Specification: Routing & Dispatching System v2.1

> ระบบจัดคิวและเส้นทางรถขนส่ง พร้อมระบบกระจายสินค้าแบบ Real-time
> วันที่: 1 สิงหาคม 2026

---

## 1. System Overview

ระบบแบ่งเป็น 2 ส่วนหลัก:
- **Data Parser**: อ่านไฟล์ OP (PDF) → สกัดข้อมูล → JSON
- **Routing Engine**: รับ JSON → Geocoding → Distance Matrix → VRP → Route Plan

---

## 2. Data Parser (อ่านไฟล์ OP)

### 2.1 Input
- ไฟล์ PDF ใบสั่งขาย (Sales Order) จากบริษัท ทรีท็อป
- ตัวอย่าง: SO6907-017

### 2.2 Output Fields (Mandatory)

| Field | ตัวอย่าง |
|-------|---------|
| order_id | SO6907-017 |
| customer_name | ย101609ยีสต์ กะ เนย (สำนักงานใหญ่) |
| delivery_address | 23-25 ถนนจักรวรรดิ แขวงจักรวรรดิ เขตสัมพันธวงศ์ กรุงเทพมหานคร 10100 |
| delivery_date | 2026-07-01 (แปลงจาก พ.ศ.) |
| po_reference | 295/14715 |
| items[].product_code | 92-0101 |
| items[].product_name | CAKE |
| items[].quantity | 1 |
| items[].unit | กล่อง |

### 2.3 Special Handling
- ชื่อลูกค้ามีตัวเลขคละกับชื่อ → ดึงทั้งสตริง
- วันที่ พ.ศ. → ลบ 543 ปี
- ที่อยู่อาจขาดคำนำหน้า → ใช้รหัสไปรษณีย์ 5 หลักตรวจสอบ
- รองรับหลาย Template ใบสั่งขาย (config ได้)

---

## 3. Geocoding & Location Validation

### 3.1 Multi-Provider Geocoding
- Primary: Google Geocoding API
- Secondary: Nominatim (OpenStreetMap) — ฟรี แต่จำกัด 1 req/sec

### 3.2 Validation Pipeline
1. Validate รูปแบบที่อยู่ไทย (เลขที่, ถนน, แขวง, เขต, จังหวัด, รหัสไปรษณีย์)
2. Check Bounding Box ไทย: Lat 5-21°N, Lon 97-106°E
3. Reverse Geocoding ย้อนกลับ → เทียบกับต้นฉบับ
4. Snap to Road API → ดึงพิกัดให้ติดถนน
5. คำนวณ Confidence Score

### 3.3 Confidence Score Algorithm
- 2 providers ตรงกัน (<50m): 100%
- 1 provider: 50%
- ห่าง 50-200m: 80%
- ห่าง 200-500m: 60%
- ห่าง >500m: 30%
- นอก Bounding Box: 0%
- Reverse Geocode ตรงกับต้นฉบับ: +10%
- Snap to Road ห่าง >1km: -20%

### 3.4 User Verification Flow
- Confidence < 70% → บังคับยืนยันบนแผนที่ (ลาก Pin ได้)
- Confidence >= 70% → แจ้งเตือนเบาๆ
- เก็บ raw_geocode_lat/lng และ verified_lat/lng แยกกัน

---

## 4. Database Schema

### 4.1 Core Tables

```sql
-- ออเดอร์
orders (order_id, customer_name, delivery_address, delivery_date, 
        po_reference, raw_geocode_lat, raw_geocode_lng, 
        verified_lat, verified_lng, confidence_score, 
        is_verified, verified_by, verified_at, status)

-- รายการสินค้า
order_items (item_id, order_id, product_code, product_name, 
             quantity, unit, weight_per_unit_kg)

-- รถ
vehicles (vehicle_id, plate_number, max_weight_kg, max_volume_cbm, 
          max_boxes, max_stops, current_weight, current_volume, 
          current_boxes, current_stops, override_enabled, 
          override_reason, override_by, driver_line_id)

-- เส้นทาง
routes (route_id, vehicle_id, status, planned_stops, 
        completed_stops, total_distance_km, total_estimated_time_min)

-- จุดส่ง
route_stops (stop_id, route_id, order_id, sequence, status, 
             scheduled_arrival, actual_arrival, scheduled_departure, 
             actual_departure, pod_image_url, failure_reason, 
             failure_note, gps_arrived_lat, gps_arrived_lng)

-- สถานะย้อนหลัง
stop_status_history (id, stop_id, status, timestamp, updated_by, note)

-- ส่งสินค้าราย item
item_deliveries (id, stop_id, item_id, ordered_qty, 
                 delivered_qty, status, note)

-- ย้าย stop ระหว่างรถ
route_transfers (id, stop_id, order_id, from_route_id, to_route_id, 
                 from_vehicle_id, to_vehicle_id, transfer_type, 
                 reason, approved_by, created_at)

-- ตำแหน่งรถ real-time
vehicle_locations (vehicle_id, lat, lng, speed_kmh, heading, recorded_at)
```

---

## 5. VRP Routing Engine

### 5.1 Input
- พิกัดทุกจุด (verified_lat/lng)
- ข้อมูลรถ (capacity, time window)
- Distance Matrix (จาก Google Distance Matrix หรือ OSRM)

### 5.2 Constraints
- Vehicle Capacity (น้ำหนัก, ปริมาตร, กล่อง, stops)
- Time Window ลูกค้า
- Max Travel Time/Distance ต่อรถ

### 5.3 Optimization
- ใช้ Google OR-Tools (Python)
- Objective: Minimize ระยะทางรวม + จำนวนรถ + ความล่าช้า

### 5.4 Performance Guardrails
- **Clustering**: ถ้า >200 stops → แบ่งเป็น zone (K-Means) แล้วคำนวณแยก
- **Timeout**: หยุดหลัง 60 วินาที ส่งคำตอบที่ดีที่สุดในตอนนั้น
- **Resource Limit**: จำกัด RAM/CPU
- **Constraint Validation**: เช็คก่อนคำนวณ (time window ไม่ทับซ้อนผิด, capacity ไม่ติดลบ)

### 5.5 Output
- Route Plan: sequence จุดส่งต่อรถ, ETA แต่ละจุด, ระยะทางรวม

---

## 6. Dynamic Vehicle Capacity (REQ-1)

### 6.1 ฟีเจอร์
- Admin กำหนด capacity รถแต่ละคันได้อิสระ
- Dispatcher ย้าย stop ระหว่างรถได้ (drag-and-drop)
- Validate ก่อนย้าย: ต้องไม่เกิน capacity
- Override ได้ในกรณีฉุกเฉิน (บันทึกเหตุผล + audit log)

### 6.2 Utilization Display
- สีเขียว: <70%
- สีเหลือง: 70-90%
- สีแดง: >90%
- สีม่วง: >100% (override)

---

## 7. Delivery Status Tracking (REQ-2)

### 7.1 Stop Status
```
PENDING → IN_TRANSIT → ARRIVED → DELIVERED
                    ↘ FAILED / PARTIAL / RESCHEDULED
```

### 7.2 Driver Actions
- กด "ถึงแล้ว" (ARRIVED)
- กด "ส่งสำเร็จ" (DELIVERED) + ถ่ายรูป POD
- กด "ส่งไม่สำเร็จ" (FAILED) + เลือกเหตุผล
- กรอกจำนวนที่ส่งจริง (PARTIAL)
- กด "Report Wrong Pin" (ส่งพิกัดจริง + รูป + หมายเหตุ)

### 7.3 Auto-Detect
- GPS เข้าใกล้จุดส่ง 100m → อัปเดต ARRIVED อัตโนมัติ
- รถหยิดนานผิดปกติ → แจ้งเตือน Dispatcher

---

## 8. Dynamic Load Balancing (REQ-3)

### 8.1 Auto-Detection
- รถเต็ม: utilization >= 90% → แจ้งเตือน
- รถว่างเกิน: utilization <= 40% → แจ้งเตือน

### 8.2 กรณีที่ 1: รถเต็ม → กระจายออก
1. หา stop ที่เหมาะสมย้ายออก (ไม่ใช่ VIP, time window ยาว)
2. หารถเป้าหมาย: utilization <80%, อยู่ในรัศมี X กม., ทิศทางเดียวกัน
3. คำนวณ Transfer Score
4. Dispatcher ยืนยันก่อน execute

### 8.3 กรณีที่ 2: รถว่าง → รับเข้า
1. หารถข้างเคียงที่บรรทุกเยอะ (>=75%)
2. หา stop ที่ใกล้เส้นทางรถว่าง
3. ตรวจสอบว่ารถว่างไม่เกิน 85% หลังย้าย
4. Dispatcher ยืนยันก่อน execute

### 8.4 Transfer Score Formula
```
score = (detour_km × 10) + (detour_min × 2) + time_window_penalty + customer_penalty - capacity_bonus

ถ้า time_window ไม่ทัน → score = 9999 (ตัดทิ้ง)
ถ้า target อยู่ที่ 60-80% → -20 (โบนัส)
ถ้า source เหลือ <30% หลังย้าย → +30 (โทษ)
```

### 8.5 Constraints การย้าย
- Time Window ต้องไม่เสีย
- อย่าแบ่งออเดอร์เดียวกัน (ถ้าไม่จำเป็น)
- รถเป้าหมายไม่เกิน 85%
- รถต้นทางเหลือไม่น้อยกว่า 30%
- อยู่ในรัศมีที่สมเหตุสมผล (เช่น <5 กม.)
- ทิศทางสอดคล้องกัน (ไม่วนกลับ)
- ประเภทสินค้าตรง (ถ้ารถแช่เย็น)

### 8.6 หลังยืนยันการย้าย
- อัปเดต route_stops
- Re-calculate route ทั้ง 2 รถ
- อัปเดต ETA ใหม่
- แจ้งเตือนคนขับทั้ง 2 คัน
- บันทึก log ใน route_transfers

---

## 9. Reschedule (ส่งไม่สำเร็จ → วันถัดไป)

- สถานะ RESCHEDULED ใน State Machine
- ย้าย stop กลับเข้า Queue รอจัดส่งวันถัดไป
- บันทึกเหตุผลการ reschedule
- แจ้งเตือนลูกค้า (ถ้ามีข้อมูลติดต่อ)

---

## 10. LINE Messaging Integration

### 10.1 ส่งให้คนขับ
- สมัคร LINE Official Account
- สร้าง Channel + เอา Channel Access Token
- เก็บ LINE User ID คนขับในฐานข้อมูล
- ส่ง Push Message: ข้อมูลออเดอร์ + ลิงก์ Google Maps

### 10.2 ข้อความที่ส่ง
```
📦 ใบสั่งขาย: SO6907-017
🏠 ลูกค้า: ย101609ยีสต์ กะ เนย
📍 ที่อยู่: 23-25 ถนนจักรวรรดิ
📦 สินค้า: CAKE 1 กล่อง, CREAM 2 กล่อง
🗺️ นำทาง: https://www.google.com/maps/dir/?api=1&destination=13.7563,100.5018
⏰ กำหนดส่ง: 09:00-12:00
```

### 10.3 ค่าใช้จ่าย
- Free Tier: 1,000 ข้อความ/เดือน
- Basic: 1,280 บาท/เดือน (15,000 ข้อความ)
- Pro: 1,780 บาท/เดือน (35,000 ข้อความ)

---

## 11. API Endpoints

### Parser
```
POST /api/parse-op          # อัปโหลด PDF → ส่ง JSON
GET  /api/orders            # ดูรายการออเดอร์
GET  /api/orders/{id}       # ดูรายละเอียดออเดอร์
```

### Geocoding
```
POST /api/geocode           # แปลงที่อยู่ → พิกัด
POST /api/validate-location  # ตรวจสอบพิกัด
POST /api/snap-to-road      # ดึงพิกัดติดถนน
```

### Routing
```
POST /api/routes/optimize   # คำนวณเส้นทาง (VRP)
GET  /api/routes/{id}       # ดูเส้นทาง
GET  /api/routes/{id}/stops # ดูรายการจุดส่ง
```

### Vehicle & Capacity
```
GET    /api/vehicles/{id}/capacity
PUT    /api/vehicles/{id}/capacity
POST   /api/vehicles/{id}/override
```

### Load Balancing
```
POST /api/balance/check-overflow
POST /api/balance/suggest-transfer
POST /api/balance/execute-transfer
GET  /api/vehicles/nearby?lat=&lng=
```

### Stop & Status
```
GET    /api/stops/{id}
GET    /api/stops/{id}/status-history
PATCH  /api/stops/{id}/status
POST   /api/stops/{id}/pod
```

### LINE
```
POST /api/line/send-route   # ส่งเส้นทางให้คนขับ
```

---

## 12. Tech Stack

| ส่วน | เทคโนโลยี |
|------|----------|
| Backend | Python + FastAPI |
| PDF Parser | pdfplumber / PyMuPDF |
| VRP Engine | Google OR-Tools |
| Database | **PostgreSQL (DECIMAL(10,8) สำหรับ lat)** — รองรับ SQLite สำหรับ dev |
| Cache | **In-memory dict + persistent location memory** (Redis optional for production) |
| Geocoding | Google Maps API + Nominatim |
| Frontend | React (Vite) + Nginx (Docker) |
| Driver Mobile | Responsive Web (PWA) |
| LINE | LINE Messaging API |
| Container | **Docker + Docker Compose** |
| Hosting | VPS / AWS EC2 / Docker Host |

---

## 13. Estimated Costs (ต่อเดือน)

| สถานการณ์ | 10 คัน | 30 คัน | 100 คัน |
|-----------|--------|--------|---------|
| Google Maps API | 300-500 บาท | 1,500-2,500 บาท | 8,000-15,000 บาท |
| LINE API | ฟรี | ฟรี-200 บาท | 500-1,500 บาท |
| Email (SES) | ฟรี | ฟรี | 50-200 บาท |
| Server/VPS | 500-700 บาท | 700-1,500 บาท | 1,500-3,000 บาท |
| Database + Redis | 0-300 บาท | 500-1,000 บาท | 1,000-2,000 บาท |
| Domain + SSL | 100-300 บาท | 100-300 บาท | 100-300 บาท |
| **รวม** | **~900-1,800 บาท** | **~2,800-5,550 บาท** | **~11,150-21,000 บาท** |

---

## 14. Phased Development Plan

| Phase | สัปดาห์ | สิ่งที่ทำ | สถานะ |
|-------|--------|----------|-------|
| 0 | 0 | Fix Debt: requirements.txt, dead code, OR-Tools, tests, config cleanup | ✅ เสร็จแล้ว |
| 1 | 1-2 | Parser + Geocoding + Database Schema | ✅ เสร็จแล้ว |
| 2 | 3-4 | VRP Engine + OR-Tools + Distance Matrix + ETA | ✅ เสร็จแล้ว |
| 3 | 5 | **PostgreSQL Migration + Docker Setup** | ✅ เสร็จแล้ว |
| 4 | 6-7 | Delivery Status Tracking + Driver Mobile Web + State Machine | ⬜ |
| 5 | 8-9 | Dynamic Capacity + Load Balancing + Reschedule | ⬜ |
| 6 | 10-11 | LINE Integration + Admin Dashboard + Security | [~] LINE notifier + endpoints สร้างแล้ว |
| 7 | 12 | Test + Debug + Deploy + Optimization | ⬜ |

---

## 15. Acceptance Criteria

- [ ] Parser ดึงข้อมูลครบจาก PDF ได้ >95%
- [ ] ทุกออเดอร์มี Confidence Score
- [ ] Confidence <70% ต้องยืนยันพิกัดก่อน VRP
- [ ] พิกัดใช้ใน Distance Matrix ผ่าน Snap to Road แล้ว
- [ ] ผู้ใช้ลาก Pin แก้ไขตำแหน่งได้
- [ ] คนขับ Report พิกัดผิด → อัปเดตถาวรได้
- [ ] Admin ดู Location Quality Report + Heatmap ได้
- [ ] ระบบประมวลผล 1,000 ออเดอร์/ชม. โดยไม่ timeout
- [ ] Dispatcher ย้าย stop ระหว่างรถได้ (drag-and-drop)
- [ ] ระบบ block การย้ายถ้าเกิน capacity
- [ ] ระบบ detect รถเต็ม/ว่าง และ suggest ย้ายได้
- [ ] Dispatcher ยืนยันก่อน execute การย้ายเสมอ
- [ ] คนขับกด ARRIVED/DELIVERED/FAILED ผ่าน mobile ได้
- [ ] ส่งไม่สำเร็จ → reschedule ไปวันถัดไปได้
- [ ] ส่งลิงก์เส้นทางให้คนขับผ่าน LINE ได้
- [ ] Unit Test ครอบคลุม >=80%
