"""
Authentication & Authorization
Phase 1: API Key header check
Phase 2: JWT + RBAC (admin/dispatcher/driver)
Phase 3: bcrypt password hashing
"""

import hmac
import logging
import os
import secrets
import sys
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

# ─── Password Hashing ──────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ─── Configuration ────────────────────────────────────────────────

# API Keys from environment
API_KEYS = os.getenv("API_KEYS", "").split(",")
API_KEYS = [key.strip() for key in API_KEYS if key.strip()]

# JWT Configuration
PRODUCTION_MODE = os.getenv("PRODUCTION_MODE", "false").lower() == "true"
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "480")
)  # 8 hours

# JWT key persistence file (dev mode only)
_JWT_SECRET_FILE = os.path.join(os.path.dirname(__file__), ".jwt_secret")

if PRODUCTION_MODE and not JWT_SECRET_KEY:
    logger.critical("FATAL: JWT_SECRET_KEY must be set in production! Exiting.")
    sys.exit(1)

if not JWT_SECRET_KEY:
    # Try to load from file for persistence across restarts
    if os.path.exists(_JWT_SECRET_FILE):
        with open(_JWT_SECRET_FILE, "r") as f:
            JWT_SECRET_KEY = f.read().strip()
        logger.info("Loaded JWT_SECRET_KEY from .jwt_secret file")
    if not JWT_SECRET_KEY:
        JWT_SECRET_KEY = secrets.token_hex(32)
        try:
            old_umask = os.umask(0o077)  # Only owner can read/write
            try:
                with open(_JWT_SECRET_FILE, "w") as f:
                    f.write(JWT_SECRET_KEY)
            finally:
                os.umask(old_umask)
            logger.info("Generated and saved JWT_SECRET_KEY to .jwt_secret file")
        except OSError:
            logger.warning(
                "Could not save JWT_SECRET_KEY to file — tokens will not persist across restarts"
            )
    logger.warning("Set JWT_SECRET_KEY env var for production use!")

# API Key header
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# JWT Bearer
JWT_BEARER = HTTPBearer(auto_error=False)

# Role-based access control
ADMIN_KEYS = os.getenv("ADMIN_KEYS", "").split(",")
ADMIN_KEYS = [key.strip() for key in ADMIN_KEYS if key.strip()]

DISPATCHER_KEYS = os.getenv("DISPATCHER_KEYS", "").split(",")
DISPATCHER_KEYS = [key.strip() for key in DISPATCHER_KEYS if key.strip()]


# ─── JWT Token Functions ──────────────────────────────────────────


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """สร้าง JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_jwt_token(token: str) -> dict:
    """ตรวจสอบ JWT token และคืนค่า payload"""
    # ตรวจ revoked (logout) ก่อน — best-effort in-memory store
    if token in _REVOKED_TOKENS:
        raise HTTPException(status_code=401, detail="Token has been revoked")
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return payload
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")


# In-memory revoked-token set (best-effort; not shared across workers).
# Used by main.py logout -> auth.revoke_token(token).
_REVOKED_TOKENS: set[str] = set()


def revoke_token(token: str) -> None:
    """เพิกถอน JWT token (logout) — เก็บใน memory ของ process นี้"""
    _REVOKED_TOKENS.add(token)


# ─── Authentication Functions ─────────────────────────────────────


def _key_in_list(key: str, key_list: list[str]) -> bool:
    """Constant-time key comparison to prevent timing attacks."""
    return any(hmac.compare_digest(key, k) for k in key_list)


def get_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    """Validate API Key from header"""
    if not API_KEYS:
        logger.critical(
            "No API_KEYS configured — denying all requests. Set API_KEYS env var."
        )
        raise HTTPException(
            status_code=500, detail="Server misconfiguration: API_KEYS not set"
        )

    if api_key and _key_in_list(api_key, API_KEYS):
        return api_key

    raise HTTPException(status_code=401, detail="Invalid or missing API Key")


def get_current_user(request: Request) -> dict:
    """ดึงข้อมูลผู้ใช้จาก JWT token หรือ API Key"""
    # ลอง JWT token ก่อน
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        payload = verify_jwt_token(token)
        username = payload.get("sub")
        db_user = _get_db_user(username)
        if db_user:
            return db_user
        # JWT valid but user not found — don't fall through to API key
        raise HTTPException(status_code=401, detail="User not found")

    # ลอง API Key
    api_key = request.headers.get("X-API-Key")
    if api_key:
        if ADMIN_KEYS and _key_in_list(api_key, ADMIN_KEYS):
            return {"username": "admin", "role": "admin", "name": "Admin (API Key)"}
        elif DISPATCHER_KEYS and _key_in_list(api_key, DISPATCHER_KEYS):
            return {
                "username": "dispatcher",
                "role": "dispatcher",
                "name": "Dispatcher (API Key)",
            }
        elif _key_in_list(api_key, API_KEYS):
            return {"username": "api_user", "role": "user", "name": "API User"}

    raise HTTPException(status_code=401, detail="Not authenticated")


def _get_db_user(username: str) -> dict | None:
    """ค้นหาผู้ใช้จากตาราง users ในฐานข้อมูล"""
    try:
        from database.db import SessionLocal
        from database.models import User as UserModel

        db = SessionLocal()
        try:
            row = (
                db.query(UserModel)
                .filter(UserModel.username == username, UserModel.is_active == True)
                .first()
            )
            if not row:
                return None
            return {
                "id": row.id,
                "username": row.username,
                "role": row.role,
                "name": row.name or row.username,
            }
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"DB user lookup failed: {e}")
        return None


def validate_password_complexity(password: str) -> None:
    """ตรวจสอบความซับซ้อนของรหัสผ่าน — 8+ ตัวอักษร มีพิมพ์ใหญ่ พิมพ์เล็ก และตัวเลข"""
    if not password or len(password) < 8:
        raise HTTPException(status_code=400, detail="รหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร")
    if not any(c.isupper() for c in password):
        raise HTTPException(status_code=400, detail="รหัสผ่านต้องมีตัวพิมพ์ใหญ่อย่างน้อย 1 ตัว")
    if not any(c.islower() for c in password):
        raise HTTPException(status_code=400, detail="รหัสผ่านต้องมีตัวพิมพ์เล็กอย่างน้อย 1 ตัว")
    if not any(c.isdigit() for c in password):
        raise HTTPException(status_code=400, detail="รหัสผ่านต้องมีตัวเลขอย่างน้อย 1 ตัว")


def verify_admin_key(api_key: str = Depends(get_api_key)) -> str:
    """ตรวจสอบ API Key สำหรับ admin"""
    if not ADMIN_KEYS:
        logger.warning("ADMIN_KEYS not configured — denying admin access")
        raise HTTPException(
            status_code=403, detail="Admin keys not configured. Set ADMIN_KEYS env var."
        )

    if _key_in_list(api_key, ADMIN_KEYS):
        return api_key

    raise HTTPException(
        status_code=403, detail="Insufficient permissions - admin access required"
    )


def verify_dispatcher_key(api_key: str = Depends(get_api_key)) -> str:
    """ตรวจสอบ API Key สำหรับ dispatcher"""
    if not DISPATCHER_KEYS and not ADMIN_KEYS:
        logger.warning("DISPATCHER_KEYS not configured — denying dispatcher access")
        raise HTTPException(
            status_code=403,
            detail="Dispatcher keys not configured. Set DISPATCHER_KEYS env var.",
        )

    if (DISPATCHER_KEYS and _key_in_list(api_key, DISPATCHER_KEYS)) or (
        ADMIN_KEYS and _key_in_list(api_key, ADMIN_KEYS)
    ):
        return api_key

    raise HTTPException(
        status_code=403, detail="Insufficient permissions - dispatcher access required"
    )


def require_role(allowed_roles: list[str]):
    """Dependency factory สำหรับตรวจสอบ role"""

    def role_checker(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required roles: {', '.join(allowed_roles)}",
            )
        return user

    return role_checker


# ─── Login Function ───────────────────────────────────────────────

# Brute-force protection: per-username lockout
_login_attempts: dict[str, list] = {}  # {username: [timestamp, ...]}
_MAX_ATTEMPTS = 5
_LOCKOUT_MINUTES = 15


def _check_login_lockout(username: str) -> None:
    """ตรวจสอบว่า username ถูกล็อกจากการพยายาม login ผิดหลายครั้ง"""
    from datetime import datetime, timedelta

    now = datetime.now(UTC)
    if username in _login_attempts:
        # ลบ attempts เก่ากว่า LOCKOUT_MINUTES
        _login_attempts[username] = [
            ts
            for ts in _login_attempts[username]
            if now - ts < timedelta(minutes=_LOCKOUT_MINUTES)
        ]
        if len(_login_attempts[username]) >= _MAX_ATTEMPTS:
            raise HTTPException(
                status_code=429, detail=f"บัญชีถูกล็อก กรุณาลองใหม่ใน {_LOCKOUT_MINUTES} นาที"
            )


def _record_login_failure(username: str) -> None:
    """บันทึกความล้มเหลวในการ login"""
    from datetime import datetime

    if username not in _login_attempts:
        _login_attempts[username] = []
    _login_attempts[username].append(datetime.now(UTC))


def _clear_login_attempts(username: str) -> None:
    """ลบประวัติ attempts เมื่อ login สำเร็จ"""
    _login_attempts.pop(username, None)


def authenticate_user(username: str, password: str) -> dict | None:
    """ตรวจสอบ username/password — เช็คตาราง users ในฐานข้อมูลเท่านั้น"""
    from database.db import SessionLocal
    from database.models import User as UserModel

    db = SessionLocal()
    try:
        row = (
            db.query(UserModel)
            .filter(UserModel.username == username, UserModel.is_active == True)
            .first()
        )
        if row and pwd_context.verify(password, row.password_hash):
            return {
                "id": row.id,
                "username": row.username,
                "role": row.role,
                "name": row.name or row.username,
            }
    finally:
        db.close()
    return None


def create_user(
    username: str,
    password: str,
    role: str = "user",
    name: str = "",
    email: str = "",
    phone: str = "",
    department: str = "",
    position: str = "",
) -> dict:
    """สร้างผู้ใช้ในฐานข้อมูล (bcrypt hash) — ใช้สำหรับ production"""
    from database.db import SessionLocal
    from database.models import User as UserModel

    if role not in ("admin", "dispatcher", "driver", "user"):
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}")

    validate_password_complexity(password)

    db = SessionLocal()
    try:
        existing = db.query(UserModel).filter(UserModel.username == username).first()
        if existing:
            raise HTTPException(
                status_code=409, detail=f"User '{username}' already exists"
            )
        user = UserModel(
            username=username,
            password_hash=pwd_context.hash(password),
            role=role,
            name=name or username,
            email=email,
            phone=phone,
            department=department,
            position=position,
            is_active=True,
        )
        db.add(user)
        db.commit()
        logger.info(f"User created: {username} (role={role})")
        return user.to_dict()
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create user {username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create user")
    finally:
        db.close()


def list_users_from_db() -> list[dict]:
    """ดึงรายชื่อผู้ใช้ทั้งหมดจากฐานข้อมูล"""
    from database.db import SessionLocal
    from database.models import User as UserModel

    db = SessionLocal()
    try:
        rows = db.query(UserModel).order_by(UserModel.username).all()
        return [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "name": u.name or u.username,
                "email": u.email or "",
                "phone": u.phone or "",
                "department": u.department or "",
                "position": u.position or "",
                "is_active": u.is_active,
            }
            for u in rows
        ]
    except Exception as e:
        logger.warning(f"DB user list failed: {e}")
        return []
    finally:
        db.close()


def login_user(username: str, password: str) -> dict:
    """Login และคืนค่า JWT token"""
    _check_login_lockout(username)

    user = authenticate_user(username, password)
    if not user:
        _record_login_failure(username)
        logger.warning(f"Failed login attempt for username: {username}")
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    _clear_login_attempts(username)
    logger.info(f"Successful login: {username} (role={user['role']})")
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"], "user_id": user["id"]}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "name": user["name"],
        },
    }
