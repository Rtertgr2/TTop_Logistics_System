# Logistics Route Planning System

เอกสารภาพรวมโครงการภาษาไทย อ้างอิงจากโค้ดและ configuration ปัจจุบันของ repository

**สถานะเอกสาร:** อ้างอิง implementation ปัจจุบัน

**วันที่อัปเดต:** 14 สิงหาคม 2026

---

## 1. ภาพรวมโครงการ

Logistics Route Planning System เป็นระบบจัดการงานขนส่งแบบครบวงจรสำหรับผู้วางแผนเส้นทาง ผู้จัดส่ง และคนขับรถ ระบบรับใบสั่งขายจาก PDF หรือ Excel แล้วแปลงเป็นข้อมูลออเดอร์ ตรวจสอบพิกัด คำนวณเส้นทางตามข้อจำกัดของรถ และติดตามสถานะการส่งสินค้า

กระบวนการหลักของระบบคือ:

```text
PDF/Excel order
    -> Extract order data
    -> Validate order data
    -> Geocode address
    -> Verify location confidence
    -> Optimize routes with vehicle constraints
    -> Save route plan
    -> Dispatch route to driver
    -> Track delivery status and GPS arrival
    -> Balance vehicle loads and notify drivers
```

ระบบรองรับการใช้งานผ่าน Dispatcher Dashboard และ Driver Mobile บน browser มือถือ

---

## 2. วัตถุประสงค์และขอบเขต

### เป้าหมายของระบบ

- ลดเวลาการจัดเส้นทางด้วยการคำนวณอัตโนมัติ
- ลดความผิดพลาดจากการอ่านใบสั่งขายด้วยมือ
- ตรวจสอบว่าพิกัดลูกค้ามีความน่าเชื่อถือก่อนนำไปวางแผน
- ควบคุมข้อจำกัดของรถ เช่น น้ำหนัก ปริมาตร กล่อง และจำนวนจุดส่ง
- ให้คนขับเห็นเส้นทางและอัปเดตสถานะจากโทรศัพท์
- เก็บประวัติการเปลี่ยนสถานะและการย้ายงานระหว่างรถ
- รองรับการใช้งานจริงด้วย PostgreSQL, Redis, Celery, HTTPS และระบบ monitoring

### ขอบเขตที่ทำงานอยู่ในปัจจุบัน

- อ่านข้อมูลออเดอร์จาก PDF และ Excel
- แปลงที่อยู่เป็นพิกัดด้วยหลาย provider
- คำนวณ confidence score และแก้พิกัดด้วยมือ
- คำนวณ CVRPTW ด้วย OR-Tools
- คำนวณ ETA และสร้าง Google Maps link
- จัดการ state ของการจัดส่ง
- ตรวจสอบรถเต็มหรือรถว่างเกินไป
- ย้าย stop ระหว่างรถพร้อมตรวจ capacity
- ส่งข้อความแจ้งเตือนผ่าน LINE
- ตรวจ GPS และเปลี่ยนสถานะเป็น `ARRIVED` อัตโนมัติ
- Snap พิกัดเข้าถนนแบบเลือกเปิดใช้ได้
- JWT, RBAC, API key, CSRF, rate limit และ security headers
- ฟังก์ชันพื้นฐานสำหรับ PDPA/GDPR

### ขอบเขตที่ยังไม่สมบูรณ์

- ฟังก์ชัน PDPA ที่มีอยู่เป็นส่วนทางเทคนิค ยังไม่ใช่กระบวนการทางกฎหมายทั้งหมด
- GPS auto-arrival ต้องได้รับ browser geolocation permission และต้องใช้ secure origin ใน production
- Snap to Road ใช้ Google Roads API ซึ่งมี quota และค่าใช้บริการ
- Backend test coverage รวมอยู่ประมาณ 51% ยังต่ำกว่าเป้าหมาย 80%
- Frontend มี Playwright smoke test แต่ยังไม่มี full user journey test ครบทุกหน้า

---

## 3. สถาปัตยกรรมระบบ

ระบบแบ่งเป็น frontend, backend API, database, cache/queue, external providers และ monitoring services

```text
                         +----------------------+
                         | Dispatcher Dashboard |
                         | Driver Mobile        |
                         +----------+-----------+
                                    |
                             HTTPS / REST API
                                    |
                         +----------v-----------+
                         | Traefik / Nginx      |
                         | CORS / API routing   |
                         +----------+-----------+
                                    |
                         +----------v-----------+
                         | FastAPI Backend      |
                         | Auth + RBAC          |
                         | Order APIs           |
                         | Route APIs           |
                         | Delivery APIs        |
                         +----+------------+----+
                              |            |
                    +---------v--+    +----v---------+
                    | PostgreSQL |    | Redis         |
                    | Operational|    | Cache/Broker  |
                    | data       |    +----+---------+
                    +------------+         |
                                      +-----v------+
                                      | Celery     |
                                      | Workers    |
                                      +------------+

       Google Maps / Roads / Esri / Nominatim / LINE Messaging API
```

### ส่วนประกอบหลัก

| ส่วน | หน้าที่ |
|---|---|
| `frontend/` | React single-page application สำหรับ dispatcher และ driver |
| `backend/main.py` | สร้าง FastAPI app, startup lifecycle และ middleware |
| `backend/api/routes.py` | REST endpoints ของระบบ |
| `backend/auth.py` | JWT, bcrypt, API keys, RBAC และ login lockout |
| `backend/database/` | SQLAlchemy models, sessions และ domain queries |
| `backend/services/` | Business logic และ external integrations |
| PostgreSQL | เก็บข้อมูลออเดอร์ รถ คนขับ แผนเส้นทาง และ audit records |
| Redis | Cache, task status และ Celery broker/result backend ตาม environment |
| Celery | ประมวลผล route optimization และ geocoding แบบ asynchronous |
| Traefik/Nginx | TLS termination, reverse proxy และ frontend serving |
| Prometheus/Grafana | Metrics และ operational dashboards |

---

## 4. เทคโนโลยีที่ใช้

| Layer | เทคโนโลยี |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy, Pydantic |
| Frontend | React 18, Vite 8.2.1, Tailwind CSS 4 |
| Database | PostgreSQL 16 สำหรับ production |
| Development DB | SQLite สำหรับ local test fallback |
| Optimization | OR-Tools 9.10, CVRPTW, Guided Local Search |
| Geocoding | Google Maps, Esri, Nominatim |
| Routing APIs | Google Distance Matrix และ Google Roads API |
| Queue | Redis และ Celery |
| Authentication | JWT, bcrypt, API key และ RBAC |
| Messaging | LINE Messaging API |
| Testing | pytest, pytest-cov และ Playwright |
| CI | GitHub Actions, Gitleaks, Ruff และ PostgreSQL service |
| Deployment | Docker Compose, Traefik และ Nginx |

---

## 5. โครงสร้าง Repository

```text
Logistics_System/
├── backend/
│   ├── api/routes.py
│   ├── auth.py
│   ├── config.py
│   ├── main.py
│   ├── celery_app.py
│   ├── tasks.py
│   ├── database/
│   ├── services/
│   ├── middleware/
│   ├── tests/
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/components/
│   ├── src/context/
│   ├── src/api.js
│   ├── tests/
│   ├── playwright.config.js
│   ├── package.json
│   └── package-lock.json
├── load-tests/
│   ├── api-smoke.js
│   └── README.md
├── monitoring/
├── docker-compose.yml
├── docker-compose.prod.yml
├── .github/workflows/ci.yml
├── .env.example
├── README.md
├── requirement_specification_v2_1.md
└── project.md
```

### จุดเริ่มต้นของ Backend

`backend/main.py` เป็น entry point ของ FastAPI application

เมื่อ application startup จะ:

- เรียก `init_db()`
- สร้างตารางที่ยังไม่มี
- ตรวจสอบและเพิ่ม column ที่ขาดตาม migration list
- เปิด middleware และ routers

### จุดเริ่มต้นของ Frontend

`frontend/src/main.jsx` mount React application ไปยัง `#root` ใน `index.html`

`frontend/src/api.js` patch global `fetch` เพื่อแนบ JWT เฉพาะ same-origin request

---

## 6. กระบวนการทำงานหลัก

## 6.1 Login และ RBAC

1. ผู้ใช้ส่ง username และ password ไปที่ `POST /api/v1/auth/login`
2. Backend ตรวจสอบ login lockout ตาม username
3. Backend อ่าน user ที่ active จาก PostgreSQL
4. Backend ตรวจสอบ password ด้วย bcrypt
5. Backend สร้าง JWT ที่มี `sub`, `role`, `user_id`, `exp` และ `jti`
6. Frontend เก็บ token ใน local storage ผ่าน `AuthContext`
7. `api.js` แนบ token ใน `Authorization: Bearer <token>` สำหรับ same-origin request
8. Backend ตรวจสอบ token และโหลด role ปัจจุบันจาก database

Role ที่มี:

| Role | สิทธิ์หลัก |
|---|---|
| `admin` | จัดการผู้ใช้ รถ ข้อมูลระบบ และ PDPA purge |
| `dispatcher` | อัปโหลดออเดอร์ คำนวณ route และ load balancing |
| `driver` | ดู route ของตัวเอง อัปเดตสถานะ และส่ง GPS arrival |
| `user` | อ่านข้อมูลที่ได้รับอนุญาต |

Backend ใช้ role จาก database เป็นหลัก ไม่เชื่อ role claim ใน JWT โดยตรง ทำให้ผู้ที่แก้ payload ของ JWT ไม่สามารถเพิ่มสิทธิ์ตัวเองได้

---

## 6.2 Upload และ PDF extraction

Endpoint หลักคือ `POST /api/v1/upload` และ `POST /api/v1/upload-multiple`

ขั้นตอนทำงาน:

1. อ่านไฟล์แบบ chunked เพื่อตรวจ file size limit
2. ตรวจ magic bytes ของไฟล์ PDF
3. ตรวจจำนวนหน้า PDF
4. เรียก `extract_pdf()` จาก `services/pdf_extractor.py`
5. แยก customer, address, order number, weight, product และ time window
6. ตรวจข้อมูลด้วย `validate_orders()`
7. เรียก geocoding engine
8. บันทึกออเดอร์และ order items ลง database
9. คืน order IDs และข้อมูลที่ frontend ใช้แสดงผล

ข้อจำกัดหลัก:

- `MAX_FILE_SIZE_MB` กำหนดขนาดไฟล์สูงสุด
- `MAX_PDF_PAGES` กำหนดจำนวนหน้าสูงสุด
- `PlanRoutesRequest.orders` จำกัดไม่เกิน 1,000 รายการ

---

## 6.3 Geocoding และ confidence score

`services/geocoding.py` ใช้ลำดับ provider ดังนี้:

1. Google Places Text Search
2. Google Geocoding
3. Esri World Geocoding
4. OpenStreetMap Nominatim
5. fallback ไปยัง depot เมื่อไม่พบผลลัพธ์ที่ใช้งานได้

ระบบตรวจว่าพิกัดอยู่ใน Thailand bounding box ก่อนยอมรับผลลัพธ์

ผลลัพธ์ geocoding มีข้อมูลสำคัญ เช่น:

- `lat`, `lng`
- `raw_lat`, `raw_lng`
- `verified_lat`, `verified_lng`
- `formatted_address`
- `geocode_provider`
- `confidence_score`
- `is_verified`

ระบบเก็บ customer location ที่ยืนยันแล้วไว้ใน `customer_locations` เพื่อใช้ลดการเรียก API ในอนาคต

---

## 6.4 Route optimization

Endpoint:

```text
POST /api/v1/plan-routes
POST /api/v1/plan-routes/async
```

ขั้นตอน synchronous:

1. รับ orders และ depot
2. ตรวจสอบโครงสร้าง order และพิกัด
3. โหลด vehicle configuration
4. สร้าง distance matrix จาก Google หรือ Haversine fallback
5. เลือก demand mode เช่น weight หรือ stop count
6. สร้าง OR-Tools routing model
7. ใส่ capacity constraint
8. ใส่ time-window constraint ถ้ามีข้อมูล
9. ใช้ search strategy และ local search
10. คำนวณลำดับจุดส่ง ETA น้ำหนักรวม และ Google Maps link
11. บันทึก `RoutePlan` และ `RouteDetail`

เมื่อใช้ `/async` งานจะเข้า Celery และ frontend ใช้ task status endpoint ตรวจสอบความคืบหน้า

### ข้อจำกัดการวางแผน

| Configuration | ความหมาย |
|---|---|
| `SOLVE_TIMEOUT_SECONDS` | เวลาสูงสุดของ solver |
| `MAX_ROUTE_DISTANCE_KM` | ระยะทางสูงสุดที่ยอมรับ |
| `MAX_STOPS_BEFORE_CLUSTER` | จำนวนจุดก่อนแบ่ง cluster |
| `AVG_SPEED_KMH` | ความเร็วเฉลี่ยสำหรับ ETA |
| `PRIORITY_TIME_COST_WEIGHT` | น้ำหนักของเวลาเดินทางใน objective |
| `PRIORITY_STOP_COST_WEIGHT` | penalty ของจำนวน stop ใน objective |

---

## 6.5 Delivery status state machine

สถานะที่ระบบรองรับ:

```text
PENDING -> IN_TRANSIT -> ARRIVED
                         -> DELIVERED
                         -> FAILED -> RESCHEDULED -> PENDING
                         -> PARTIAL -> DELIVERED
                                  -> FAILED
```

สถานะ `DELIVERED` เป็น terminal state

ทุกการเปลี่ยนสถานะจะ:

- ตรวจ transition ที่อนุญาต
- แก้ `stops_json`
- บันทึก timestamp และผู้แก้ไข
- เพิ่มแถวใน `stop_status_history`
- เก็บ note สำหรับ failed หรือ partial delivery

---

## 6.6 GPS auto-arrival

Endpoint:

```text
POST /api/v1/delivery/auto-arrive
```

ตัวอย่าง request:

```json
{
  "route_id": 1,
  "stop_id": 1,
  "lat": 13.7500,
  "lng": 100.5000,
  "accuracy_m": 5,
  "event_id": "optional-client-event-id"
}
```

ระบบจะ:

1. ตรวจ JWT และตรวจว่า driver เป็นเจ้าของ route หรือไม่
2. ตรวจพิกัดและ GPS accuracy
3. lock `RouteDetail` ใน database ที่รองรับ row lock
4. ค้นหา stop ตาม `id` หรือ `order_number`
5. ใช้ `verified_lat/verified_lng` ก่อน `lat/lng`
6. คำนวณ Haversine distance
7. ยอมรับเมื่ออยู่ใน `AUTO_ARRIVAL_RADIUS_M` ซึ่งค่าเริ่มต้นคือ 100 เมตร
8. ยอมรับเฉพาะสถานะ `IN_TRANSIT`
9. เปลี่ยนเป็น `ARRIVED`
10. บันทึก `arrival_source`, GPS point, accuracy, distance และ event ID
11. เพิ่มประวัติสถานะเพียงครั้งเดียว

การส่งสัญญาณซ้ำหลังสถานะเป็น `ARRIVED` จะคืนผลสำเร็จแบบ idempotent และไม่สร้าง history ซ้ำ

Driver Mobile ใช้ `navigator.geolocation.watchPosition()` และส่งข้อมูลไม่ถี่กว่า 15 วินาทีต่อครั้ง ระบบยังคงมีปุ่ม manual status สำหรับกรณีผู้ใช้ไม่อนุญาต geolocation

---

## 6.7 Snap to Road

Endpoint:

```text
POST /api/v1/snap-to-road
```

ตัวอย่าง request:

```json
{
  "points": [
    {"lat": 13.7500, "lng": 100.5000}
  ]
}
```

ระบบรองรับ 1 ถึง 100 จุดต่อ request

`services/road_snapping.py` เรียก Google Nearest Roads API และคืนค่า:

- input coordinate
- snapped coordinate
- ระยะห่างระหว่าง input กับ snapped
- Google `place_id` ถ้ามี
- provider
- `snapped` boolean
- fallback reason ถ้าไม่สามารถ snap ได้

Fallback จะใช้พิกัดเดิมเมื่อ:

- ปิด feature
- ไม่มี Google API key
- API timeout, 429 หรือ 5xx
- API ไม่คืนจุด
- จุดที่ snap อยู่นอกประเทศไทย
- ระยะ snap เกิน `SNAP_TO_ROAD_MAX_DISTANCE_M`

ค่า `SNAP_TO_ROAD_ENABLED=false` ปิดการ snap อัตโนมัติใน distance matrix เป็นค่าเริ่มต้น เนื่องจาก Google Roads API เป็นบริการที่มีค่าใช้จ่าย ส่วน endpoint ที่ผู้ใช้เรียกโดยตรงเป็น explicit operation

---

## 6.8 Load balancing

ระบบคำนวณ utilization ของแต่ละ route จาก:

- น้ำหนักรวมของ stops
- ความจุรถ
- จำนวน stops

สถานะของรถคือ `overflow`, `underflow`, `high` หรือ `normal`

เมื่อพบ imbalance ระบบจะสร้าง transfer suggestions โดยพิจารณา:

- น้ำหนักของ stop
- ระยะเบี่ยงเบนจาก centroid
- เวลาเบี่ยงเบนโดยประมาณ
- ความจุที่เหลือของรถปลายทาง
- time window risk
- น้ำหนักขั้นต่ำที่รถต้นทางต้องเหลือ

การ execute transfer จะ:

- ตรวจว่า source และ target ไม่ใช่ route เดียวกัน
- ตรวจ route และ stop ที่มีอยู่จริง
- ตรวจ target ไม่เกิน 95% capacity
- ตรวจ source หลังย้ายไม่ต่ำกว่า 30% capacity
- resequence stops
- บันทึก `RouteTransfer`

---

## 6.9 LINE notification

ระบบใช้ LINE Messaging API แบบ push:

1. ผู้ดูแลกรอก `LINE User ID` ในข้อมูลรถหรือคนขับ
2. Dispatcher เลือก route หรือ vehicle
3. Backend สร้างข้อความสรุป route
4. Backend ส่ง Google Maps link, plate, driver, น้ำหนัก และจำนวนจุดส่ง
5. ระบบจำกัดข้อความไม่เกินขนาดที่ LINE รองรับ

LINE webhook จะ reject request ถ้าไม่มี `LINE_CHANNEL_SECRET` หรือ signature ไม่ถูกต้อง

การสมัคร LINE Official Account และการออก access token เป็นขั้นตอนภายนอก repository

---

## 7. โครงสร้างฐานข้อมูล

ข้อมูล operational หลักอยู่ใน PostgreSQL โดย SQLAlchemy เป็น ORM

| Model | หน้าที่ |
|---|---|
| `User` | ผู้ใช้และสิทธิ์ |
| `AuditLog` | ประวัติการจัดการผู้ใช้ |
| `Order` | ออเดอร์ลูกค้า |
| `OrderItem` | รายการสินค้าในออเดอร์ |
| `Vehicle` | ข้อมูลรถและ capacity |
| `Product` | master product |
| `RoutePlan` | แผนจัดส่งระดับวัน |
| `RouteDetail` | route ของรถแต่ละคันและ `stops_json` |
| `CustomerLocation` | พิกัดลูกค้าที่จำไว้ |
| `Driver` | โปรไฟล์คนขับ |
| `VehicleLoad` | load ปัจจุบันของรถ |
| `StopStatusHistory` | ประวัติสถานะ stop |
| `ItemDelivery` | สถานะการส่งระดับสินค้า |
| `RouteTransfer` | audit การย้าย stop |
| `VehicleLocation` | พิกัด GPS รถ |

ปัจจุบัน `RouteDetail.stops_json` เก็บรายละเอียด stop เป็น JSON ภายใน route record จึงทำให้การแก้ route และ status อยู่ใน transaction เดียวได้ แต่ query เชิง analytics จะซับซ้อนกว่าการมีตาราง stop แยก

---

## 8. API สำคัญ

API ทั้งหมดอยู่ใต้ `/api/v1` ยกเว้น health, metrics และ LINE legacy webhook บาง path Swagger อยู่ที่ `/docs`

### ระบบยืนยันตัวตน

```text
POST /api/v1/auth/login
POST /api/v1/auth/logout
GET  /api/v1/auth/me
GET  /api/v1/auth/users
GET  /api/v1/auth/employees
POST /api/v1/auth/employees
PUT  /api/v1/auth/employees/{user_id}
PUT  /api/v1/auth/employees/{user_id}/password
PUT  /api/v1/auth/employees/{user_id}/toggle-active
```

### ออเดอร์และเส้นทาง

```text
POST /api/v1/upload
POST /api/v1/upload-multiple
POST /api/v1/plan-routes
POST /api/v1/plan-routes/async
GET  /api/v1/orders-history
GET  /api/v1/orders/today
POST /api/v1/orders/assign-date
GET  /api/v1/routes/today
GET  /api/v1/history
```

### การจัดส่ง

```text
GET  /api/v1/delivery/driver/{driver_name}
POST /api/v1/delivery/update-status
POST /api/v1/delivery/auto-arrive
GET  /api/v1/delivery/status-history/{route_id}
GET  /api/v1/delivery/dashboard
GET  /api/v1/delivery/summary
POST /api/v1/delivery/update-item
POST /api/v1/delivery/reschedule
GET  /api/v1/delivery/valid-transitions/{current_status}
```

### รถขนส่งและการกระจายงาน

```text
GET    /api/v1/vehicles
PUT    /api/v1/vehicles
DELETE /api/v1/vehicles/{vehicle_id}
GET    /api/v1/load-balance/analyze
GET    /api/v1/load-balance/suggestions
POST   /api/v1/load-balance/execute
```

### แผนที่และความเป็นส่วนตัว

```text
GET    /api/v1/search-place
GET    /api/v1/reverse-geocode
POST   /api/v1/orders/{order_id}/verify-location
POST   /api/v1/snap-to-road
GET    /api/v1/privacy-policy
GET    /api/v1/auth/export-data
DELETE /api/v1/auth/delete-data
POST   /api/v1/admin/purge-data
```

### จุดเชื่อมต่อของระบบ

```text
GET /health
GET /metrics
GET /docs
```

---

## 9. Frontend และ Driver Mobile

Frontend เป็น React SPA ประกอบด้วยหน้าหลักดังนี้:

| Component | หน้าที่ |
|---|---|
| `LoginScreen` | Login ด้วย username/password |
| `Dashboard` | สรุปข้อมูลการจัดส่ง |
| `FileUpload` | Upload PDF/Excel |
| `Orders` | ดูและจัดการออเดอร์ |
| `MapView` | แสดงพิกัดและ route บน Leaflet |
| `RouteResult` | แสดงผล route และข้อมูลรถ |
| `VehicleManager` | จัดการรถ คนขับ capacity และ LINE ID |
| `DriverMobile` | หน้า mobile สำหรับคนขับ |
| `LoadBalancer` | วิเคราะห์และย้ายงานระหว่างรถ |
| `BookingDashboard` | จัดการวันจัดส่ง |
| `EmployeeManager` | จัดการผู้ใช้และ audit log |
| `NotificationPanel` | แสดง notifications |
| `AdminDashboard` | ข้อมูลสำหรับ admin |

Driver Mobile ทำงานดังนี้:

1. โหลด route ของคนขับจาก `/delivery/driver/{name}`
2. แสดง stop และ filter ตามสถานะ
3. เปิด Google Maps navigation
4. อัปเดตสถานะด้วย manual action
5. เริ่ม browser GPS watcher เมื่อ stop เป็น `IN_TRANSIT`
6. ส่ง GPS ไปที่ `/delivery/auto-arrive`
7. หยุด watcher เมื่อเปลี่ยน stop, logout หรือ unmount

---

## 10. Security และ PDPA

### การควบคุมความปลอดภัยที่ทำแล้ว

| Control | รายละเอียด |
|---|---|
| Password hashing | bcrypt ผ่าน Passlib |
| JWT | อายุเริ่มต้น 60 นาทีและมี JTI |
| Token revocation | ใช้ Redis เมื่อเปิดใช้ และ in-memory fallback สำหรับ development |
| RBAC | `admin`, `dispatcher`, `driver`, `user` |
| API keys | เปรียบเทียบแบบ constant-time |
| CSRF | ตรวจ Origin/Referer โดยไม่ bypass ด้วย auth header |
| Rate limiting | in-memory ต่อ process ใน implementation ปัจจุบัน |
| Security headers | CSP, HSTS, X-Frame-Options, nosniff และ Permissions-Policy |
| File upload protection | จำกัดขนาด ตรวจ PDF magic bytes และจำกัดจำนวนหน้า |
| Audit logging | HTTP audit logs และ user-management audit records |
| Webhook verification | HMAC signature สำหรับ LINE webhook |
| Secret scanning | Gitleaks ใน GitHub Actions |
| Container hardening | production compose ใช้ non-root และจำกัด capabilities |

### การควบคุมทางเทคนิคของ PDPA

- `consent_given`
- `consent_date`
- `privacy_policy_version`
- Data export endpoint
- Data erasure endpoint
- Retention purge function
- Celery Beat daily retention task
- Public privacy-policy metadata endpoint
- Anonymization และ account deactivation ระหว่าง erasure

### ข้อจำกัดสำคัญ

- Endpoint ทางเทคนิคไม่ใช่โครงการ PDPA ที่สมบูรณ์ตามกฎหมาย
- องค์กรต้องกำหนด lawful basis และวิธีขอ consent เอง
- PII ยังคงอยู่ใน operational tables จนกว่าจะผ่าน retention หรือ erasure process
- Encryption at rest ของ database, Redis, volume และ backup ต้องตั้งค่าที่ infrastructure
- Rate limiting และ login lockout แบบ Redis ยังจำเป็นสำหรับ deployment หลาย worker
- Flower ยังต้องเพิ่ม authentication ก่อนเปิดใช้ production

### การจัดการ secret

ไฟล์ `.env` ถูก ignore โดย Git และไม่พบเป็น tracked file หรือใน repository history จากการตรวจครั้งนี้ เอกสารนี้ไม่มีค่า secret จริง อย่างไรก็ตามควร rotate ค่า Google Maps, LINE, database และ JWT ก่อนนำ environment เดิมไปใช้ production

---

## 11. Testing และ CI/CD

### การทดสอบ Backend

Backend tests ใช้ pytest และแบ่งเป็น:

- Pure function tests
- Authentication และ RBAC tests
- Database CRUD tests
- FastAPI integration tests
- External API mock tests
- Delivery state และ GPS tests
- Snap to Road tests
- PDPA tests

ผลล่าสุดบน PostgreSQL 16:

```text
290 passed
1 warning จาก Starlette/httpx compatibility
```

Coverage ล่าสุดประมาณ 51% โดยจุดที่ยังต่ำคือ API routes, route database operations, PDF extraction, Celery tasks และ Excel export

### การทดสอบ Frontend

Playwright smoke test ตรวจ:

- หน้าเว็บเปิดได้
- title ถูกต้อง
- หน้า login แสดง
- username และ password fields แสดง

ผลล่าสุด:

```text
1 passed
```

### กระบวนการ CI

ลำดับงานใน `.github/workflows/ci.yml` คือ:

```text
secret-scan -> lint -> PostgreSQL tests + coverage -> frontend E2E -> Docker build
```

CI ใช้ `USE_SQLITE_TEST_DB=false` เพื่อให้ tests ใช้ PostgreSQL service จริง

### คำสั่งทดสอบ

```bash
cd backend
python -m pytest tests/ -v
```

รันทดสอบบน PostgreSQL:

```bash
USE_SQLITE_TEST_DB=false \
DATABASE_URL=postgresql://logistics:testpassword@localhost:5432/logistics_test \
python -m pytest tests/ -v --cov=. --cov-report=term-missing
```

รัน frontend:

```bash
cd frontend
npm ci
npm run build
npm run e2e
```

---

## 12. Configuration และ Environment Variables

| Variable | ค่าเริ่มต้น | หน้าที่ |
|---|---:|---|
| `DATABASE_URL` | ขึ้นกับ environment | PostgreSQL หรือ SQLite connection URL |
| `PRODUCTION_MODE` | `false` | เปิด production guards |
| `JWT_SECRET_KEY` | generated ใน dev | JWT signing secret |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | อายุ JWT |
| `API_KEYS` | empty | General API keys |
| `ADMIN_KEYS` | empty | Admin API keys |
| `DISPATCHER_KEYS` | empty | Dispatcher API keys |
| `GOOGLE_MAPS_API_KEY` | empty | Google geocoding, matrix และ Roads APIs |
| `LINE_CHANNEL_ACCESS_TOKEN` | empty | LINE push token |
| `LINE_CHANNEL_SECRET` | empty | LINE webhook signature secret |
| `LINE_DEFAULT_USER_ID` | empty | ผู้รับ LINE เริ่มต้น |
| `DEPOT_ADDRESS` | depot กรุงเทพฯ | ที่อยู่ depot |
| `DEPOT_LAT` | `13.781882` | latitude ของ depot |
| `DEPOT_LNG` | `100.425041` | longitude ของ depot |
| `MAX_FILE_SIZE_MB` | `10` | ขนาดไฟล์สูงสุด |
| `MAX_PDF_PAGES` | `200` | จำนวนหน้า PDF สูงสุด |
| `BUSINESS_TIMEZONE` | `Asia/Bangkok` | timezone สำหรับคำนวณวันทำงาน |
| `SOLVE_TIMEOUT_SECONDS` | `30` | เวลาสูงสุดของ OR-Tools |
| `MAX_ROUTE_DISTANCE_KM` | `200` | ระยะทาง route สูงสุด |
| `MAX_STOPS_BEFORE_CLUSTER` | `200` | threshold สำหรับแบ่ง cluster |
| `AVG_SPEED_KMH` | `30` | ความเร็วเฉลี่ยสำหรับ ETA |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `REDIS_ENABLED` | `false` | เปิด Redis cache |
| `REDIS_CACHE_TTL` | `3600` | อายุ cache |
| `AUTO_ARRIVAL_RADIUS_M` | `100` | ระยะตรวจ GPS ถึงจุดส่ง |
| `AUTO_ARRIVAL_MAX_ACCURACY_M` | `100` | GPS accuracy สูงสุดที่ยอมรับ |
| `SNAP_TO_ROAD_ENABLED` | `false` | เปิด snap ใน distance matrix |
| `SNAP_TO_ROAD_MAX_DISTANCE_M` | `1000` | ระยะ snap สูงสุด |
| `SNAP_TO_ROAD_MAX_POINTS` | `100` | จำนวนจุดต่อ request |
| `SNAP_TO_ROAD_TIMEOUT_SECONDS` | `3` | timeout ของ Roads API |
| `DATA_RETENTION_DAYS` | `365` | ระยะเก็บออเดอร์ |
| `PRIVACY_POLICY_VERSION` | `1.0` | version ของ policy ที่ consent |
| `DPO_CONTACT_EMAIL` | empty | อีเมลผู้ติดต่อด้าน privacy |
| `ALLOWED_ORIGINS` | localhost origins | CORS และ CSRF origins |
| `RATE_LIMIT_PER_MINUTE` | `60` | rate limit แบบ in-memory |

`USE_SQLITE_TEST_DB` เป็น test-only variable ค่า `true` ให้ local tests ใช้ SQLite ค่า `false` ต้องใช้ `DATABASE_URL` ที่ชี้ PostgreSQL

---

## 13. การรันระบบ

### การพัฒนาด้วย Docker

```bash
cp .env.example .env
  --username admin \
  --role admin \
  --name "Administrator"
```

เปิด frontend ที่ `http://localhost:3000`

คำสั่งที่ใช้บ่อย:

```bash
```

### การพัฒนาโดยไม่ใช้ Docker

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

เปิดอีก terminal:

```bash
cd frontend
npm ci
npm run dev
```

### การใช้งาน Production ด้วย Docker Compose

```bash
cp .env.example .env
```

ก่อนเปิด production ต้องตั้งค่าอย่างน้อย:

- `POSTGRES_PASSWORD`
- `REDIS_PASSWORD`
- `JWT_SECRET_KEY`
- `GOOGLE_MAPS_API_KEY`
- `DOMAIN`
- `ACME_EMAIL`
- `ALLOWED_ORIGINS`
- `PRODUCTION_MODE=true`

สร้าง admin คนแรก:

```bash
  --username admin \
  --role admin \
  --name "Administrator"
```

---

## 14. Backup, Monitoring และ Operations

Production compose มี service สำหรับ:

- PostgreSQL
- Redis
- FastAPI backend
- Celery worker
- Celery Flower
- Frontend
- Traefik
- Docker socket proxy
- Prometheus
- Grafana

Backup PostgreSQL ตัวอย่าง:

```bash
  | gzip > backups/backup-$(date +%Y%m%d-%H%M).sql.gz
```

ตรวจสุขภาพ:

```bash
```

Grafana และ Flower ไม่ได้เปิด port สู่ host โดยตรงใน production compose ที่มีอยู่ ควรเข้าผ่าน tunnel หรือ reverse proxy ที่มี authentication

---

## 15. การทดสอบโหลด

`load-tests/api-smoke.js` ใช้ k6 ตรวจ endpoint พื้นฐานสองตัว:

- `/health`
- `/api/v1/privacy-policy`

รันกับ non-production environment ก่อน:

```bash
k6 run \
  -e BASE_URL=http://localhost:8000 \
  -e VUS=5 \
  -e DURATION=30s \
  load-tests/api-smoke.js
```

อย่าเพิ่ม VUs หรือ duration บน production จนกว่าจะยืนยัน database, reverse proxy, rate limit และ quota ของ external API

---

## 16. สถานะงานปัจจุบัน

| หมวด | สถานะ | รายละเอียด |
|---|---|---|
| Backend หลัก | เสร็จสำหรับขอบเขตปัจจุบัน | order, route, delivery, fleet และ notification flows ทำงานแล้ว |
| การเสริมความปลอดภัย | ทำแล้วเป็นส่วนใหญ่ | แก้จุดเสี่ยงหลักแล้ว |
| ส่วนทางเทคนิคของ PDPA | ทำแล้ว | export, erasure, retention และ consent fields |
| GPS auto-arrival | ทำแล้ว | backend endpoint, driver watcher และ tests |
| Snap to Road | ทำแล้ว | explicit endpoint, optional matrix integration และ tests |
| การตรวจสอบ PostgreSQL | ผ่าน | 290 tests ผ่านบน PostgreSQL 16 |
| E2E ของ Frontend | มี baseline | Playwright smoke test ผ่าน 1 รายการ |
| การทดสอบโหลด | มี baseline | มี k6 script แต่ไม่ได้รันอัตโนมัติ |
| Backend coverage | ต้องเพิ่ม | ประมาณ 51% |
| Ruff ของ Backend | ต้อง cleanup | มี legacy lint debt เหลืออยู่ |
| Lint ของ Frontend | ทำงานแต่มี warnings | มี unused imports และ console warnings เดิม |
| การหมุน secret จริง | รอดำเนินการ | ต้องทำใน external environments |

---

## 17. งานที่เหลือ

### ต้องทำก่อน production

- Rotate Google Maps API key
- Rotate LINE channel access token และ channel secret
- Rotate PostgreSQL password
- Rotate JWT secret
- ยืนยันว่า production `.env` อยู่นอก Git และมี file permission ที่จำกัด
- รัน GitHub Actions ทั้งชุดและต้องให้ผลเป็นสีเขียว
- ตั้ง Redis password และเปิด Redis ใน production
- เพิ่ม authentication ให้ Flower

### งานที่ควรทำต่อ

- เพิ่ม backend coverage จากประมาณ 51% ไปใกล้ 80%
- เพิ่ม API tests สำหรับ upload, async tasks, route planning, export และ Excel generation
- เพิ่ม Celery task tests
- เพิ่ม PDF fixture tests จากเอกสารลูกค้าหลายรูปแบบ
- เพิ่ม frontend tests สำหรับ login, upload, map verification, route results และ GPS permission states
- ย้าย rate limiting และ login lockout ไป Redis สำหรับ multi-worker deployment
- ลด PII ที่ส่งกลับ API และเพิ่ม PII access audit records
- เพิ่ม encryption-at-rest ที่ PostgreSQL, Redis, volumes และ backups
- แก้ Ruff errors และ frontend warnings ที่มีอยู่เดิม
- แยก `backend/api/routes.py` เป็น routers ตาม domain
- เปลี่ยน startup column migration เป็น versioned migration เมื่อ schema เปลี่ยนบ่อยขึ้น
- เพิ่มการ monitor quota ของ Google Maps และ Roads API

### งานภายนอก repository

- สมัครและตั้งค่า LINE Official Account
- ออก Channel Access Token และ Channel Secret
- กำหนด privacy policy, lawful basis, DPO และ retention policy ให้ถูกต้องตามองค์กร

---

## 18. สรุปการทำงานทั้งระบบแบบ End-to-End

เมื่อ dispatcher เริ่มงาน ระบบรับใบสั่งขายจาก PDF หรือ Excel แล้วตรวจสอบข้อมูลก่อน geocode ที่อยู่ผ่าน provider หลายตัว ระบบเก็บ confidence score และพิกัดที่ยืนยันแล้ว จากนั้น dispatcher เลือกรถและสั่งคำนวณ route ด้วย OR-Tools ซึ่งพิจารณาความจุรถ ระยะทาง เวลา และ time window

ระบบบันทึกแผนลง PostgreSQL และส่ง route ให้คนขับผ่าน Driver Mobile คนขับสามารถเริ่มงาน เปิด Google Maps อัปเดตสถานะ และให้ browser ส่ง GPS เพื่อ auto-arrive เมื่อเข้าใกล้จุดส่ง ระบบเก็บ status history และ metadata ของการถึงจุดส่ง

หากรถคันใดเต็มหรือว่างเกิน ระบบคำนวณ transfer suggestion และบังคับ capacity guard ก่อนย้าย stop Dispatcher สามารถส่งสรุป route และ Google Maps link เข้า LINE

งาน background เช่น route optimization ขนาดใหญ่และ retention purge ทำผ่าน Celery/Redis ระบบส่ง metrics ไป Prometheus และใช้ Grafana สำหรับ monitoring

---

## 19. เอกสารอ้างอิง

| ไฟล์ | ใช้สำหรับ |
|---|---|
| `README.md` | คู่มือ setup development และ production |
| `requirement_specification_v2_1.md` | สเปกความต้องการเดิม |
| `backend/pyproject.toml` | pytest และ coverage configuration |
| `.github/workflows/ci.yml` | secret scan, lint, tests, E2E และ build pipeline |
| `.env.example` | root environment template |
| `backend/.env.example` | backend environment template |
| `load-tests/README.md` | คู่มือ k6 load test |
| `monitoring/` | Prometheus และ Grafana configuration |
