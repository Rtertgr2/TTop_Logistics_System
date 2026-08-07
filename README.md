# ระบบจัดคิวรถและเส้นทางจัดส่งอัตโนมัติ (Logistics Route Planning System)

ระบบวางแผนเส้นทางจัดส่งสินค้าอัตโนมัติแบบครบวงจร: อ่านใบสั่งขาย (PDF) → แปลงพิกัด (Geocoding) → คำนวณเส้นทาง (VRP) → จัดการสถานะส่งของ → กระจายน้ำหนักรถ (Load Balancing) → ส่งใบสั่งงาน + ลิงก์แผนที่เข้า LINE

**สถานะปัจจุบัน: ~80% (74/101 checklist items เสร็จ + 14 บางส่วน)** — อัปเดตล่าสุด 02 ส.ค. 2026 (changelog ถึง v2.10)

---

## 1. ภาพรวมระบบ (Features)

### 1.1 ข้อมูลใบสั่งขาย (PDF Parser)
- อ่านไฟล์ PDF / Excel ใบสั่งขาย (OP) อัตโนมัติ → แยกชื่อลูกค้า, ที่อยู่, น้ำหนัก, สินค้า
- รองรับอัปโหลดหลายไฟล์, เช็คขนาดไฟล์ + จำกัดจำนวนหน้า PDF (กัน file DoS)
- เก็บข้อมูลสินค้า (item) และประวัติที่มาของไฟล์

### 1.2 พิกัดที่อยู่ (Geocoding & Validation)
- Geocoding หลาย provider (Google Maps เป็นหลัก) + fallback
- **Confidence Score** — ตรวจความตรงของพิกัดจากหลายแหล่ง (ตรงกัน 2 แหล่ง = 100%)
- **Reverse Geocode** + แก้พิกัดด้วยมือ (ถูก propagate ไปทุกจุดที่ใช้)
- บันทึกพิกัดที่ยืนยันแล้ว (customer_locations) นำกลับมาใช้ใหม่

### 1.3 คำนวณเส้นทาง (VRP — OR-Tools)
- **CVRPTW** (ความจุ + กรอบเวลา) แก้ด้วย OR-Tools + Christofides + GLS
- จัดโซนอัตโนมัติเมื่อออเดอร์เยอะ (>200 จุด) → cluster ก่อนค่อยหาคำตอบ
- คำนวณ **ETA** ทุกจุดส่ง + สร้าง **ลิงก์ Google Maps นำทาง** ให้อัตโนมัติ
- Dynamic vehicle capacity (น้ำหนัก / ปริมาตร / จำนวนกล่อง / จำนวนจุดส่ง)
- **Plan routes แบบ async** (Celery queue) สำหรับงานใหญ่ + tracking สถานะ

### 1.4 จัดการสถานะส่งของ (Delivery Status)
- คนขับอัปเดตสถานะ: `DELIVERED` / `FAILED` / `PARTIAL` (ส่งไม่ครบ) ผ่าน **Driver Mobile**
- บันทึกประวัติสถานะทุกครั้ง (Stop Status History) + หมายเหตุ
- **Reschedule** — ส่งไม่สำเร็จ → ส่งต่อวันถัดไป
- แดชบอร์ดสรุปผลส่งของ (Delivery Dashboard) แยกตามรถ/คนขับ

### 1.5 กระจายน้ำหนักรถ (Load Balancing)
- ย้าย stop ระหว่างรถ แบบเช็ค capacity อัตโนมัติ (ห้าม overfill >95%)
- กันการย้ายจน source เหลือน้อยเกินไป (<30%) — เหลือไว้ส่งจริง
- จัดสรรงานใหม่ (rebalance) หลัง optimize

### 1.6 การแจ้งเตือน LINE (ส่งลิงก์แผนที่)
- เก็บ **LINE User ID ต่อรถ/คนขับ** ในหน้า "จัดการรถ"
- ปุ่ม **"ส่ง LINE ให้คนขับ"** ต่อคัน → ส่งลิงก์ Google Maps + สรุปใบสั่งงานเข้าบัญชี LINE คนขับ
- ฝั่ง backend ใช้ LINE **Messaging API** (push) — ตั้งค่าผ่าน `LINE_CHANNEL_ACCESS_TOKEN`

### 1.7 ความปลอดภัย & ผู้ใช้
- **JWT + RBAC** (admin / dispatcher / driver / user) — ตรวจสิทธิ์ทุก endpoint
- ผู้ใช้เก็บในฐานข้อมูล 100% (ไม่มี default users / ไม่มี backdoor) — สร้างผ่าน `manage_users.py`
- API Key รองรับ (แยก role) · rate limiting · CSRF protection · mask API key ใน log

### 1.8 ระบบสนับสนุน (Production)
- **Queue**: Celery + Redis (plan-routes async)
- **Monitoring**: Prometheus + Grafana (dashboard + metric)
- **DB**: PostgreSQL 16 · **HTTPS**: Traefik + Let's Encrypt

---

## 2. สถาปัตยกรรม

| ส่วน | เทคโนโลยี |
|------|----------|
| Backend | FastAPI (Python 3.11), SQLAlchemy, OR-Tools VRP, Celery |
| Frontend | React + Vite (Dispatcher Dashboard + Driver Mobile) |
| Database | PostgreSQL 16 (Docker volume) |
| Cache/Queue | Redis 7 (queue + task status) |
| Reverse Proxy | Traefik (auto HTTPS Let's Encrypt) |
| Monitoring | Prometheus + Grafana (ภายใน) |
| Auth | JWT + RBAC (admin/dispatcher/driver) + bcrypt, API Keys |

### โครงสร้างโฟลเดอร์หลัก

```
Logistics_System/
├── backend/                  # FastAPI backend
│   ├── main.py               # entry point + startup (init_db, middleware)
│   ├── auth.py               # JWT, bcrypt, RBAC dependencies
│   ├── manage_users.py       # CLI สร้าง/ลิสต์ผู้ใช้
│   ├── config.py             # ตัวแปร env ทั้งหมด
│   ├── api/routes.py         # REST API ทุก endpoint
│   ├── database/             # models.py + db.py (SQLAlchemy)
│   ├── services/             # route_optimizer (VRP), load_balancer,
│   │                         # geocoding, distance_matrix, line_notifier,
│   │                         # notifications, cache, excel_exporter
│   ├── celery_app.py         # Celery + tasks (optimize/geocode async)
│   ├── tests/                # 48 pytest (unit)
│   └── Dockerfile
├── frontend/                 # React + Vite (SPA)
│   └── src/components/       # Dashboard, FileUpload, RouteResult, MapView,
│                             # VehicleManager, DriverMobile, LoadBalancer,
│                             # DatabaseViewer, AdminDashboard, LoginScreen
├── docker-compose.yml        # dev stack (db, backend, frontend)
├── docker-compose.prod.yml   # production stack (10 บริการ)
├── monitoring/               # Prometheus + Grafana config
├── HANDOFF.md                # โครงสร้าง + API reference + remaining issues
├── master_checklist_routing_system.md  # รายการงานทั้งหมด + changelog
└── README.md                 # เอกสารนี้
```

---

## 3. เอกสารอ้างอิง

| ไฟล์ | ใช้สำหรับ |
|------|-----------|
| `HANDOFF.md` | สถาปัตยกรรม, API reference, known issues, version history |
| `master_checklist_routing_system.md` | รายการงานทั้งหมด + สถานะ + changelog ทุกเวอร์ชัน |
| `requirement_specification_v2_1.md` | สเปกความต้องการเดิม |
| `monitoring/` | Prometheus config + Grafana provisioning + dashboard |

---

# 🖥️ การรันระบบ (Development)

## วิธีที่ 1 — Docker (แนะนำ)

```bash
# 1) สร้าง .env
cp .env.example .env
# แก้ค่าอย่างน้อย: POSTGRES_PASSWORD, JWT_SECRET_KEY, GOOGLE_MAPS_API_KEY

# 2) Build + Start
docker compose up -d --build

# 3) สร้างผู้ใช้คนแรก (ระบบไม่มี default users)
docker compose exec backend python manage_users.py create --username admin --role admin --name "Administrator"
# ระบบจะถามรหัสผ่านจาก stdin

# 4) เข้าใช้งาน
open http://localhost:3000
```

| หน้า | URL |
|------|-----|
| ระบบหลัก (frontend) | http://localhost:3000 |
| API (เรียกผ่าน proxy) | `http://localhost:3000/api/v1/...` (nginx ต่อให้ backend อัตโนมัติ) |
| API Docs (Swagger) | เข้าภายใน container: `docker compose exec backend curl -L http://localhost:8000/docs` |
| Health check | เข้าภายใน container: `docker compose exec backend curl http://localhost:8000/health` |

**คำสั่งที่ใช้บ่อย:**
```bash
docker compose ps                 # ดูสถานะทุก service
docker compose logs -f backend    # ดู log backend
docker compose down               # หยุดระบบ (ข้อมูลใน volume คงอยู่)
docker compose up -d --build      # เปิดใหม่ (หลังแก้โค้ด)
```

### หมายเหตุสำคัญ
- **ข้อมูลรถเริ่มต้นว่าง** — ต้องเข้าเมนู "จัดการรถ" แล้วกรอกข้อมูลรถจริง (ทะเบียน/คนขับ/น้ำหนัก/LINE User ID) ก่อนกดคำนวณเส้นทาง
- ปุ่ม "ล้างข้อมูลทั้งหมด" จะลบเฉพาะออเดอร์/ประวัติเส้นทาง — **ไม่ลบข้อมูลรถ**
- รหัสผ่านถูกถามผ่าน stdin (ไม่ปรากฏบนจอ) — ถ้าใช้ `docker compose exec` แบบ non-tty ให้ pipe password 2 ครั้งตามลำดับ

## วิธีที่ 2 — ไม่ใช้ Docker

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env
uvicorn main:app --reload        # หรือตั้ง DATABASE_URL ชี้ SQLite/Postgres

# Frontend (เปิดอีก terminal)
cd frontend
npm install
npm run dev
```

<<<<<<< Updated upstream
## API Endpoints
- `POST /upload` - อัปโหลดไฟล์ PDF
- `POST /plan-routes` - คำนวณเส้นทาง

## TEST URL
- https://adventures-proceeds-modular-hello.trycloudflare.com
=======
> ⚠️ สิ่งแวดล้อม dev นี้ใช้ Postgres เป็น default (`DATABASE_URL`) — ถ้าจะใช้ SQLite ให้ตั้ง `DATABASE_URL=sqlite:///./data/logistics.db` ก่อนรัน

---

# 🧪 Testing

```bash
cd backend
python -m pytest tests/ -v    # 48 tests (data validator, haversine, VRP, rebalance)
```

Tests เป็น unit ล้วน (ไม่ต้องรัน server/DB) — รันตรงๆ ได้เลย

---

# 📦 คู่มือติดตั้งบน Server ของลูกค้า (Production)

## 1. ข้อกำหนด Server

| รายการ | ขั้นต่ำ | แนะนำ |
|--------|--------|--------|
| OS | Ubuntu 22.04 / Debian 12 | Ubuntu 22.04 LTS |
| CPU | 2 cores | 4 cores |
| RAM | 4 GB | 8 GB |
| Disk | 20 GB SSD | 50 GB SSD |
| Software | Docker 24+ + Docker Compose v2 | ล่าสุด |
| Domain | จดโดเมน + ตั้ง DNS A record ชี้มาที่ IP server | + เปิดพอร์ต 80/443 |

> **สำคัญ:** ต้องมี domain name (เช่น `logistics.company.com`) เพื่อให้ Traefik ออก SSL ให้อัตโนมัติ (Let's Encrypt)

## 2. ติดตั้ง Docker บน Server

```bash
# ติดตั้ง Docker (Ubuntu/Debian) — ไม่ใช้ snap เพื่อเลี่ยง sandbox จำกัดการเข้าถึงไฟล์
curl -fsSL https://get.docker.com | sh

# เปิดใช้งาน service + รันตอน boot
sudo systemctl enable --now docker

# ตรวจสอบว่าใช้งานได้ (ต้องเห็น version)
docker --version
docker compose version
```

> 💡 ถ้าติดตั้งผ่าน snap (`/snap/bin/docker`) จะเข้าโฟลเดอร์ `/media`, `/mnt` ไม่ได้ → รัน `sudo snap connect docker:removable-media` เพื่อปลดล็อก หรือติดตั้งผ่าน apt ตามด้านบน

## 3. นำโปรเจคขึ้น Server

```bash
# ตัวเลือก A: clone จาก git repo
git clone <URL-repo-ของคุณ> /opt/logistics
cd /opt/logistics

# ตัวเลือก B: copy ผ่าน scp จากเครื่อง dev
# scp -r ./Logistics_System user@server-ip:/opt/logistics
```

## 4. สร้างไฟล์ `.env` (สำคัญที่สุด)

```bash
cd /opt/logistics
cp .env.example .env
```

> ⚠️ compose ใช้ `env_file: .env` — ต้อง copy เป็นชื่อ `.env` (ไม่ใช่ `.env.prod`)

แก้ไฟล์ `.env` ด้วย `nano .env` แล้วตั้งค่าทุกตัว **โดยเฉพาะ:**

```bash
# 1. เจนรหัสลับทั้งหมด (รัน 3 บรรทัดนี้ แล้วเอาค่ามาใส่ใน .env)
openssl rand -hex 32    # → ใส่ใน JWT_SECRET_KEY
openssl rand -hex 16    # → ใส่ใน REDIS_PASSWORD
openssl rand -hex 16    # → ใส่ใน POSTGRES_PASSWORD
```

| ตัวแปร | ต้องตั้งเป็น | หมายเหตุ |
|--------|-------------|----------|
| `POSTGRES_PASSWORD` | รหัสผ่าน DB | ไม่มีค่านี้ compose จะไม่ start |
| `REDIS_PASSWORD` | รหัสผ่าน Redis | ไม่มีค่านี้ compose จะไม่ start |
| `JWT_SECRET_KEY` | 64 ตัวอักษรสุ่ม | ไม่มีค่านี้ backend จะ exit ทันที |
| `DOMAIN` | `logistics.company.com` | ต้องตรงกับ DNS |
| `ACME_EMAIL` | อีเมลจริง | ใช้ตอนขอ SSL |
| `ALLOWED_ORIGINS` | `https://logistics.company.com` | ต้องตรงกับ DOMAIN ไม่งั้น browser จะโดน CSRF 403 |
| `GOOGLE_MAPS_API_KEY` | Google Maps API key | จำเป็นสำหรับ Geocoding/แผนที่ |
| `API_KEYS` / `ADMIN_KEYS` / `DISPATCHER_KEYS` | API key แยก role | ใช้สำหรับเครื่องมือภายนอก |
| `GRAFANA_PASSWORD` | รหัสผ่าน Grafana | ใช้ตอนเข้าผ่าน tunnel (ไม่เปิดพอร์ตสู่ host) |

## 5. Build + Start ระบบ

```bash
cd /opt/logistics
docker compose -f docker-compose.prod.yml up -d --build
```

รอสักครู่ (ครั้งแรก build ประมาณ 5-10 นาที) แล้วตรวจสอบว่าบริการรันครบ:

```bash
docker compose -f docker-compose.prod.yml ps
# ควรเห็น: db, redis, backend, celery-worker, celery-flower,
#          frontend, docker-proxy, traefik, prometheus, grafana
```

## 6. สร้างผู้ใช้ระบบ (Admin คนแรก)

```bash
# รันในเครื่อง server (container backend)
docker exec -it logistics-backend-prod python manage_users.py create \
  --username admin \
  --role admin \
  --name "Administrator"
# ระบบจะถามรหัสผ่านจาก stdin (ไม่แสดงบนหน้าจอ)

# ตรวจสอบรายชื่อผู้ใช้
docker exec -it logistics-backend-prod python manage_users.py list
```

| Role | สิทธิ์ |
|------|--------|
| `admin` | ใช้งานทุกหน้า รวมลบข้อมูล, จัดการรถ |
| `dispatcher` | ใช้งานหลัก: อัปโหลด, คำนวณเส้นทาง, load balancing |
| `driver` | หน้า Driver Mobile |
| `user` | อ่านข้อมูลพื้นฐาน |

สร้างผู้ใช้เพิ่ม:
```bash
docker exec -it logistics-backend-prod python manage_users.py create --username somchai --role dispatcher --name "สมชาย"
# ระบบจะถามรหัสผ่านจาก stdin
```

## 7. ตั้งค่า LINE (ส่งลิงก์แมพเข้า LINE ต่อคนขับ)

> ฝั่งโค้ดพร้อมแล้ว (ปุ่ม "ส่ง LINE ให้คนขับ" ต่อคัน) — ต้องตั้งค่าฝั่ง LINE เอง:

1. สมัคร **LINE Developers** → สร้าง Provider → สร้าง **Messaging API channel** (LINE OA)
2. ไปที่หน้า channel → **Messaging API** tab → copy **Channel Access Token** (Long-lived)
3. ใส่ค่าใน `.env`:
   ```
   LINE_CHANNEL_ACCESS_TOKEN=<token ที่ได้>
   ```
4. Restart backend: `docker compose -f docker-compose.prod.yml up -d --build backend`
5. **คนขับต้อง add LINE OA นี้เป็นเพื่อนก่อน** จึงจะรับ push ได้
6. หา **LINE User ID** ของคนขับแต่ละคน (LINE Developers console → ดู message ที่ส่งมา, หรือเปิด Use webhook รับ event) แล้วกรอกที่หน้า "จัดการรถ"

> หมายเหตุ: ระบบนี้ใช้ LINE **Messaging API** (push ทางเดียว) — ยังไม่รวม webhook / rich menu / quick reply

## 8. เข้าใช้งาน

| หน้า | URL |
|------|-----|
| ระบบหลัก | `https://logistics.company.com` |
| API (เรียกผ่าน proxy) | `https://logistics.company.com/api/v1/...` (traefik → nginx → backend) |
| API Docs (Swagger) | เข้าภายใน container: `docker exec logistics-backend-prod curl -L http://localhost:8000/docs` |

> Grafana / Flower ไม่ได้เปิดพอร์ตสู่ host (เน้นความปลอดภัย) — เข้าถึงได้ผ่าน tunnel เช่น `ssh -L 3000:localhost:3000 user@server` แล้วเปิด `http://localhost:3000` (user/password จาก `GRAFANA_ADMIN_USER`/`GRAFANA_PASSWORD` และ Flower) หรือเพิ่มบรรทัด `ports:` ชั่วคราวใน compose

## 9. Backup / Restore ฐานข้อมูล

```bash
# Backup (รันทุกวัน ผ่าน cron)
docker exec logistics-db-prod pg_dump -U logistics logistics \
  | gzip > /opt/logistics/backups/backup-$(date +%Y%m%d-%H%M).sql.gz

# Restore
gunzip -c backup-XXXX.sql.gz | docker exec -i logistics-db-prod psql -U logistics logistics
```

> ตัวอย่าง cron: `0 2 * * * docker exec logistics-db-prod pg_dump -U logistics logistics | gzip > /opt/logistics/backups/backup-\$(date +\%Y\%m\%d).sql.gz` — เก็บอย่างน้อย 14 วัน

## 10. อัปเดตระบบ (เมื่อมี code ใหม่)

```bash
cd /opt/logistics
git pull            # หรือ copy ไฟล์ใหม่เข้ามาแทน
docker compose -f docker-compose.prod.yml up -d --build
```

> หมายเหตุ: migration คอลัมน์ใหม่จะรันอัตโนมัติตอน boot (`_migrate_columns`) — ไม่ต้องทำอะไรเพิ่ม

## 11. Troubleshooting

```bash
# ดู log ของ service ใดๆ
docker logs -f logistics-backend-prod
docker logs -f logistics-celery-worker-prod

# เช็ค health endpoint (backend อยู่ใน Docker network — ต้อง exec เข้าไป)
docker exec logistics-backend-prod curl http://localhost:8000/health
# {"status": "healthy", "database": {"status": "connected"}, ...}

# ถ้า HTTPS ไม่ขึ้น: ตรวจสอบว่า DOMAIN + DNS ชี้มาถูกต้อง
dig logistics.company.com

# ถ้า browser ขึ้น 403 ตอน login: ตรวจสอบ ALLOWED_ORIGINS ตรงกับ DOMAIN
# ถ้า login ได้แต่ข้อมูล error 401: ตรวจสอบ JWT_SECRET_KEY ไม่เปลี่ยนระหว่าง restart
# ถ้า docker บอก permission denied ตอนอ่านไฟล์: docker เป็น snap → sudo snap connect docker:removable-media
# ถ้า LINE ส่งไม่ได้: คนขับยังไม่ได้ add OA เป็นเพื่อน / token ผิด / ยังไม่ได้ตั้ง LINE_CHANNEL_ACCESS_TOKEN
```

---

# 📝 สิ่งที่ยังต้องทำ (Remaining)

## ต้องทำด้วยตัวเอง (Blocked — external)
- **LINE Official Account** — สมัครที่ https://manager.line.biz + ตั้ง Channel Access Token ตามหัวข้อ 7 (items 3.3.1, 3.3.2)

## ยังไม่เริ่มจาก checklist (13 รายการ)
- **GPS auto-detect ARRIVED** (2.2.7) — ใกล้จุดส่ง → อัปเดตอัตโนมัติ
- **Drag-and-drop ย้าย stop ระหว่างรถ** + override + audit log (2.1.4–2.1.7)
- **Snap to Road API** (1.2.5) · **ตาราง vehicle_load real-time** (1.3.5) · **resource limit container** (1.4.4)
- **PDPA/GDPR compliance** (3.4.10) · LINE webhook / rich menu / quick reply (3.3.6–3.3.7)

## Hardening ค้าง (จาก Grill Me #10 audit — MEDIUM/LOW)
- pin dependencies (requirements.txt / package-lock) · Flower ใส่ auth · กัน username enumeration
- จำกัด error detail ใน 400/health · ปรับ nginx upload size ให้ตรง backend · ETA ใช้ distance matrix แทน haversine
- notification ID collision · `_batch_distance_matrix` แบ่ง batch ตาม limit API · จำกัด RAM ของ `_MATRIX_CACHE`
- validate `AVG_SPEED_KMH=0` · `cache.py` ยังไม่ถูกใช้ (หรือใช้ Redis จริง) · redirect HTTP→HTTPS ใน Traefik

---

# 📜 Changelog (ล่าสุด)

| วันที่ | เวอร์ชัน | สรุป |
|-------|----------|------|
| 02 ส.ค. 2026 | 2.10 | **ข้อมูลรถ** — ตัด seed ปลอม (เริ่มว่าง), reset ไม่ลบรถ, กรอกอิสระ, เพิ่ม `line_user_id` ต่อคัน + ปุ่มส่ง LINE ให้คนขับ |
| 02 ส.ค. 2026 | 2.9 | **Grill Me #10** — 17 จุด CRITICAL+HIGH: IDOR, mask API key, ลบ DEFAULT_USERS, timezone, capacity join, threadpool, TRUST_PROXY_HEADERS, chunked upload, ฯลฯ |
| 02 ส.ค. 2026 | 2.8 | **Production Deploy Prep** — DB-backed users, manage_users.py, API key + JWT |
| 02 ส.ค. 2026 | 2.7 | **Grill Me #8** — 7 CRITICAL: middleware, frontend auth, hooks, VRP guards |
| 02 ส.ค. 2026 | 2.6 | **Queue + Metrics** — Celery async plan, Prometheus/Grafana |

ดูรายละเอียดทั้งหมดใน `master_checklist_routing_system.md`
>>>>>>> Stashed changes
