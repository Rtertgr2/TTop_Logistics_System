import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from config import ALLOWED_ORIGINS
from database.db import init_db

# ── Logging Setup ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── App ──────────────────────────────────────────────────────────
app = FastAPI(
    title="Logistics Route Planning System",
    description="ระบบจัดคิวรถและเส้นทางจัดส่งอัตโนมัติ",
    version="1.2.0 (with SQLite DB)",
)

@app.on_event("startup")
def on_startup():
    init_db()
    logger.info("Database initialized successfully on startup")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
def root():
    return {
        "message": "Logistics Route Planning System API",
        "version": "1.1.0",
        "docs": "/docs",
    }


logger.info("Logistics Route Planning System started")
