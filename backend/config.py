import os

# App Version
APP_VERSION = os.getenv("APP_VERSION", "2.1.0")

# Google Maps API
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# LINE Messaging API
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
LINE_DEFAULT_USER_ID = os.getenv("LINE_DEFAULT_USER_ID", "")

# Depot (คลังสินค้า / ต้นทาง)
DEPOT_ADDRESS = os.getenv("DEPOT_ADDRESS", "บริษัท ทรีท็อปเคมิคัลแอนด์ฟู้ดส์ คอร์ปอเรชั่น จำกัด 20/2 ถนนบรมราชชนนี แขวงฉิมพลี เขตตลิ่งชัน กรุงเทพมหานคร 10170")
DEPOT_LAT = float(os.getenv("DEPOT_LAT", "13.781882"))
DEPOT_LNG = float(os.getenv("DEPOT_LNG", "100.425041"))

# File upload
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))
MAX_PDF_PAGES = int(os.getenv("MAX_PDF_PAGES", "200"))

# Backup
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "data", "op_backups")

# PDF Templates (1.1.11)
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "data", "templates")

# CORS
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",") if o.strip()]

# Business timezone — ใช้สำหรับคำนวณ "วันนี้" (ป้องกันข้อมูลหายตอนเที่ยงคืน UTC vs เวลาไทย)
BUSINESS_TIMEZONE = os.getenv("BUSINESS_TIMEZONE", "Asia/Bangkok")

# VRP Solver Configuration — validate against zero/negative
SOLVE_TIMEOUT_SECONDS = max(int(os.getenv("SOLVE_TIMEOUT_SECONDS", "30")), 1)
MAX_ROUTE_DISTANCE_KM = max(int(os.getenv("MAX_ROUTE_DISTANCE_KM", "200")), 1)
MAX_STOPS_BEFORE_CLUSTER = max(int(os.getenv("MAX_STOPS_BEFORE_CLUSTER", "200")), 1)
AVG_SPEED_KMH = max(int(os.getenv("AVG_SPEED_KMH", "30")), 1)

# Route optimization priority weights (objective cost = distance_m + TIME_COST_WEIGHT * travel_min + STOP_COST_WEIGHT)
# Priority order: (1) Weight = HARD capacity constraint (never exceeded),
#                  (2) Time & Distance = primary objective,
#                  (3) Number of stops = tertiary objective (small penalty)
# Tune via env vars to shift emphasis between tiers 2 and 3.
PRIORITY_TIME_COST_WEIGHT = max(int(os.getenv("PRIORITY_TIME_COST_WEIGHT", "500")), 0)
PRIORITY_STOP_COST_WEIGHT = max(int(os.getenv("PRIORITY_STOP_COST_WEIGHT", "100")), 0)

# Redis Cache Configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"
REDIS_CACHE_TTL = int(os.getenv("REDIS_CACHE_TTL", "3600"))  # 1 hour default
