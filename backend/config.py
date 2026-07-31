from dotenv import load_dotenv
import os

load_dotenv()

# Google Maps API
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# AI Refinement API (LM Studio)
LMSTUDIO_URL = os.getenv("LMSTUDIO_URL", "http://localhost:1234/v1")
ENABLE_AI_REFINEMENT = os.getenv("ENABLE_AI_REFINEMENT", "true").lower() == "true"

# Depot (คลังสินค้า / ต้นทาง)
DEPOT_ADDRESS = os.getenv("DEPOT_ADDRESS", "บริษัท ทรีท็อปเคมิคัลแอนด์ฟู้ดส์ คอร์ปอเรชั่น จำกัด 20/2 ถนนบรมราชชนนี แขวงฉิมพลี เขตตลิ่งชัน กรุงเทพมหานคร 10170")
DEPOT_LAT = float(os.getenv("DEPOT_LAT", "13.781882"))
DEPOT_LNG = float(os.getenv("DEPOT_LNG", "100.425041"))

# Email
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")

# File upload
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "10"))

# Backup
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "data", "op_backups")

# PDF Templates (1.1.11)
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "data", "templates")

# CORS
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
