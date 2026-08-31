import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api.routes import router
from auth import _key_in_list
from config import ALLOWED_ORIGINS, APP_VERSION
from database.db import get_db_status, init_db
from logging_config import setup_logging
from metrics import metrics_endpoint, metrics_middleware
from middleware.security import (
    AuditLogMiddleware,
    CSRFMiddleware,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)
from services.line_webhook import router as line_webhook_router

# ── Logging Setup ────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_JSON = os.getenv("LOG_JSON", "false").lower() == "true"
setup_logging(log_level=LOG_LEVEL, json_format=LOG_JSON)
logger = logging.getLogger(__name__)


# ── API Key Middleware ───────────────────────────────────────────


class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        from auth import API_KEYS

        self.api_keys = API_KEYS

    async def dispatch(self, request: Request, call_next):
        skip_paths = ["/health", "/", "/docs", "/openapi.json", "/redoc", "/metrics"]
        if request.url.path in skip_paths:
            return await call_next(request)

        # Skip auth endpoints (both legacy /api/auth/ and versioned /api/v1/auth/)
        if request.url.path.startswith("/api/auth/") or request.url.path.startswith(
            "/api/v1/auth/"
        ):
            return await call_next(request)

        # Skip public PDPA transparency endpoint (no auth required by design)
        if request.url.path in ("/api/v1/privacy-policy", "/api/privacy-policy"):
            return await call_next(request)

        # Skip LINE webhook (receives POST from LINE servers without auth headers)
        if request.url.path in ("/api/v1/line/webhook", "/api/line/webhook"):
            return await call_next(request)

        if request.method == "OPTIONS":
            return await call_next(request)

        if self.api_keys:
            api_key = request.headers.get("X-API-Key")
            if not api_key or not _key_in_list(api_key, self.api_keys):
                # อนุญาตผู้ใช้ที่ login ด้วย JWT (Authorization: Bearer) ให้ผ่านได้
                auth_header = request.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    from fastapi import HTTPException as _HTTPExc

                    from auth import verify_jwt_token

                    try:
                        verify_jwt_token(auth_header[7:])
                        return await call_next(request)
                    except _HTTPExc:
                        pass  # invalid JWT — fall through to 401
                return Response(
                    content='{"detail": "Invalid or missing API Key"}',
                    status_code=401,
                    media_type="application/json",
                )

        return await call_next(request)


# ── Lifespan ────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database initialized successfully on startup")
    yield
    logger.info("Application shutting down")


# ── App ──────────────────────────────────────────────────────────
app = FastAPI(
    title="Logistics Route Planning System",
    description="ระบบจัดคิวรถและเส้นทางจัดส่งอัตโนมัติ",
    version=APP_VERSION,
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-CSRF-Token"],
)

# Middleware (executed bottom-to-top: last added = first executed)
app.add_middleware(APIKeyMiddleware)


@app.middleware("http")
async def metrics(request: Request, call_next):
    """Prometheus metrics middleware (registered as HTTP middleware, not class)"""
    return await metrics_middleware(request, call_next)


# Security middleware
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(AuditLogMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=RATE_LIMIT_PER_MINUTE)
app.add_middleware(CSRFMiddleware)

# API Versioning
app.include_router(line_webhook_router, prefix="/api")
app.include_router(router, prefix="/api")


@app.middleware("http")
async def redirect_legacy_api(request: Request, call_next):
    """Redirect /api/* to /api/v1/* for backward compatibility"""
    path = request.url.path
    # Skip redirect for LINE webhook (needs exact path match)
    if path == "/api/line/webhook":
        return await call_next(request)
    if (
        path.startswith("/api/")
        and not path.startswith("/api/v1/")
        and not path.startswith("/api/auth/")
    ):
        new_path = path.replace("/api/", "/api/v1/", 1)
        return RedirectResponse(url=new_path, status_code=307)
    return await call_next(request)


@app.get("/")
def root():
    return {
        "message": "Logistics Route Planning System API",
        "version": APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
def health_check():
    """Health check endpoint — ตรวจสอบสถานะ API และ Database"""
    db_status = get_db_status()
    is_healthy = db_status["status"] == "connected"

    response = {
        "status": "healthy" if is_healthy else "unhealthy",
        "database": db_status,
        "version": APP_VERSION,
        "timestamp": db_status["timestamp"],
    }

    if not is_healthy:
        return JSONResponse(content=response, status_code=503)

    return response


@app.get("/metrics")
async def metrics_endpoint_handler():
    """Prometheus metrics endpoint"""
    return await metrics_endpoint()


logger.info("Logistics Route Planning System started")
