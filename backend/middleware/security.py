"""
Security Middleware
Rate limiting, audit logging, security headers, CSRF protection
"""

import os
import re
import time
import logging
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Trust X-Forwarded-For / X-Real-IP headers to get the real client IP.
# Set true when running behind a trusted reverse proxy (e.g. nginx in docker-compose).
TRUST_PROXY_HEADERS = os.getenv("TRUST_PROXY_HEADERS", "false").lower() == "true"

# ─── CSRF Protection ──────────────────────────────────────────────

# Allowed origins for CSRF validation
ALLOWED_ORIGINS = set(
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
    if origin.strip()
)

# Methods that require CSRF validation
CSRF_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


def _get_origin_host(origin: str) -> str:
    """Extract host from Origin header"""
    if not origin:
        return ""
    # Remove protocol
    host = origin.split("://", 1)[-1] if "://" in origin else origin
    # Remove port if present
    host = host.split("/")[0]
    return host.lower()


class CSRFMiddleware(BaseHTTPMiddleware):
    """CSRF protection via Origin/Referer header validation"""

    async def dispatch(self, request: Request, call_next):
        # Only validate mutating methods
        if request.method not in CSRF_METHODS:
            return await call_next(request)

        # Skip CSRF for login endpoints (unauthenticated) — รองรับทั้ง path ปัจจุบันและเก่า
        if request.url.path == "/api/v1/auth/login" or request.url.path == "/api/auth/login":
            return await call_next(request)

        # Skip CSRF for LINE webhook (receives POST from LINE servers without Origin)
        if request.url.path in ("/api/v1/line/webhook", "/api/line/webhook"):
            return await call_next(request)

        # Skip CSRF for docs/openapi (exact match หรือ trailing slash)
        if request.url.path.rstrip("/") in ("/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        # Check Origin header
        origin = request.headers.get("Origin", "")
        referer = request.headers.get("Referer", "")

        # Extract host from origin or referer
        check_host = _get_origin_host(origin) if origin else _get_origin_host(referer)

        if not check_host:
            # No Origin/Referer header — could be a non-browser client (curl, API key)
            # Allow if X-API-Key is present (non-browser API client)
            if request.headers.get("X-API-Key"):
                return await call_next(request)
            # Allow if Authorization header is present (JWT from non-browser)
            if request.headers.get("Authorization"):
                return await call_next(request)
            # Block browser requests without Origin
            logger.warning(f"CSRF: No Origin/Referer header from {request.client.host if request.client else 'unknown'} {request.method} {request.url.path}")
            return Response(
                content='{"detail": "Missing Origin header"}',
                status_code=403,
                media_type="application/json"
            )

        # Validate origin against allowed list
        origin_allowed = False
        for allowed in ALLOWED_ORIGINS:
            allowed_host = _get_origin_host(allowed)
            if check_host == allowed_host:
                origin_allowed = True
                break

        if not origin_allowed:
            logger.warning(f"CSRF: Invalid origin {check_host} for {request.method} {request.url.path}")
            return Response(
                content='{"detail": "Invalid origin"}',
                status_code=403,
                media_type="application/json"
            )

        return await call_next(request)


# ─── Rate Limiting ────────────────────────────────────────────────

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using in-memory store"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)  # IP -> list of timestamps
        self._cleanup_counter = 0
    
    async def dispatch(self, request: Request, call_next):
        # Get real client IP behind reverse proxy
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("X-Forwarded-For")
        real_ip = request.headers.get("X-Real-IP")

        if TRUST_PROXY_HEADERS:
            # Trusted reverse proxy (nginx) — use LAST IP in chain (added by proxy, not client-supplied)
            if forwarded_for:
                client_ip = forwarded_for.split(",")[-1].strip()
            elif real_ip:
                client_ip = real_ip.strip()
        else:
            # Only trust proxy headers if request comes from localhost (reverse proxy)
            if client_ip in ("127.0.0.1", "::1", "localhost"):
                if forwarded_for:
                    client_ip = forwarded_for.split(",")[-1].strip()
                elif real_ip:
                    client_ip = real_ip.strip()
        
        now = datetime.now(timezone.utc)
        
        # ลบ requests เก่า
        self.requests[client_ip] = [
            ts for ts in self.requests[client_ip]
            if now - ts < timedelta(minutes=1)
        ]
        
        # ตรวจสอบ rate limit
        if len(self.requests[client_ip]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return Response(
                content='{"detail": "Rate limit exceeded. Please try again later."}',
                status_code=429,
                media_type="application/json"
            )
        
        # บันทึก request
        self.requests[client_ip].append(now)
        
        # Periodic cleanup of stale IP entries (every 100 requests)
        self._cleanup_counter += 1
        if self._cleanup_counter >= 100:
            self._cleanup_counter = 0
            stale_ips = [
                ip for ip, timestamps in self.requests.items()
                if not timestamps or all(
                    now - ts >= timedelta(minutes=1) for ts in timestamps
                )
            ]
            for ip in stale_ips:
                del self.requests[ip]
        
        response = await call_next(request)
        return response


# ─── Audit Logging ────────────────────────────────────────────────

# Sensitive data patterns to mask in logs
_SENSITIVE_PATTERNS = [
    ("password", "****"),
    ("token", "****"),
    ("secret", "****"),
    ("api_key", "****"),
    ("GOOGLE_MAPS_API_KEY", "****"),
    ("LINE_CHANNEL_ACCESS_TOKEN", "****"),
    ("JWT_SECRET_KEY", "****"),
]


def _mask_sensitive_data(data: str) -> str:
    """Mask sensitive data in log strings"""
    masked = data
    for key, replacement in _SENSITIVE_PATTERNS:
        # Mask values in key=value patterns
        pattern = rf'({key}[=:]\s*)([^\s&,}}]+)'
        masked = re.sub(pattern, rf'\g<1>{replacement}', masked, flags=re.IGNORECASE)
    return masked


class AuditLogMiddleware(BaseHTTPMiddleware):
    """Audit logging middleware for security events with data masking"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path
        user_agent = request.headers.get("user-agent", "-")
        
        response = await call_next(request)
        
        duration = time.time() - start_time
        
        # Build audit log entry
        status = response.status_code
        log_entry = f"{client_ip} {method} {path} {status} {duration:.3f}s"
        
        # Log security events with appropriate severity
        if status == 401:
            logger.warning(f"AUTH_FAILED: {log_entry}")
        elif status == 403:
            logger.warning(f"FORBIDDEN: {log_entry}")
        elif status == 429:
            logger.warning(f"RATE_LIMITED: {log_entry}")
        elif status >= 500:
            logger.error(f"SERVER_ERROR: {log_entry}")
        
        # Log all API calls with masked data
        if path.startswith("/api/"):
            # Mask any sensitive query params
            query = str(request.url.query) if request.url.query else ""
            masked_query = _mask_sensitive_data(query)
            if masked_query:
                logger.info(f"API_CALL: {log_entry} query={masked_query}")
            else:
                logger.info(f"API_CALL: {log_entry}")
        
        # Log mutating operations for audit trail
        if method in ("POST", "PUT", "DELETE") and path.startswith("/api/"):
            logger.info(f"AUDIT: {client_ip} {method} {path} → {status} ({duration:.3f}s)")
        
        return response


# ─── Security Headers ─────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to responses"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # เพิ่ม security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Content Security Policy — no unsafe-inline/unsafe-eval
        csp = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https://maps.googleapis.com https://api.line.me"
        )
        response.headers["Content-Security-Policy"] = csp
        
        return response
