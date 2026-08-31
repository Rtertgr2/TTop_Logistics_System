"""Employee (User) management database operations + audit logging."""

import logging
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import func

from auth import pwd_context, validate_password_complexity
from database.db import SessionLocal
from database.models import AuditLog
from database.models import User as UserModel

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


def log_audit(
    user_id: int, username: str, action: str, target_user: str = "", details: str = ""
) -> None:
    """บันทึก audit log ลงตาราง audit_logs"""
    db = SessionLocal()
    try:
        entry = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            target_user=target_user,
            details=details,
            timestamp=datetime.now(UTC),
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to write audit log: {e}")
    finally:
        db.close()


def count_admins() -> int:
    """นับจำนวน admin ที่ยังเปิดใช้งานอยู่"""
    db = SessionLocal()
    try:
        return (
            db.query(func.count(UserModel.id))
            .filter(UserModel.role == "admin", UserModel.is_active == True)
            .scalar()
            or 0
        )
    finally:
        db.close()


def create_employee(
    username: str,
    password: str,
    role: str = "user",
    name: str = "",
    email: str = "",
    phone: str = "",
    department: str = "",
    position: str = "",
    actor: dict | None = None,
    consent_given: bool = False,
    privacy_policy_version: str = "",
) -> dict:
    """สร้างพนักงานใหม่ (admin only)"""
    if role not in ("admin", "dispatcher", "driver", "user"):
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}")

    # ห้ามสร้าง admin ถ้ามี admin อยู่แล้ว (ป้องกัน escalation)
    if role == "admin":
        existing_admins = count_admins()
        if existing_admins >= 1:
            raise HTTPException(
                status_code=403,
                detail="ไม่สามารถสร้าง admin ได้อีก — ระบบรองรับ admin เพียง 1 คนเท่านั้น",
            )

    validate_password_complexity(password)

    db = SessionLocal()
    try:
        existing = db.query(UserModel).filter(UserModel.username == username).first()
        if existing:
            raise HTTPException(
                status_code=409, detail=f"User '{username}' already exists"
            )

        from datetime import datetime

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
            consent_given=consent_given,
            consent_date=datetime.now(UTC) if consent_given else None,
            privacy_policy_version=privacy_policy_version or "",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        log_audit(
            user_id=actor.get("id", 0) if actor else 0,
            username=actor.get("username", "system") if actor else "system",
            action="create",
            target_user=username,
            details=f"role={role}, name={name}, department={department}, position={position}",
        )

        return {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "department": user.department,
            "position": user.position,
            "is_active": user.is_active,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create employee {username}: {e}")
        raise HTTPException(status_code=500, detail="Failed to create employee")
    finally:
        db.close()


def update_employee(user_id: int, updates: dict, actor: dict | None = None) -> dict:
    """อัปเดตข้อมูลพนักงาน (admin only) — ห้ามเปลี่ยน role เป็น admin"""
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้ที่ระบุ")

        # ป้องกัน role escalation: ห้ามเปลี่ยนใครก็ตามเป็น admin
        new_role = updates.get("role")
        if new_role is not None:
            if new_role == "admin" and user.role != "admin":
                raise HTTPException(
                    status_code=403, detail="ไม่สามารถเปลี่ยน role เป็น admin ได้"
                )
            if new_role not in ("admin", "dispatcher", "driver", "user"):
                raise HTTPException(status_code=400, detail=f"Invalid role: {new_role}")
            user.role = new_role

        if "name" in updates and updates["name"] is not None:
            user.name = updates["name"]
        if "email" in updates and updates["email"] is not None:
            user.email = updates["email"]
        if "phone" in updates and updates["phone"] is not None:
            user.phone = updates["phone"]
        if "department" in updates and updates["department"] is not None:
            user.department = updates["department"]
        if "position" in updates and updates["position"] is not None:
            user.position = updates["position"]

        db.commit()
        db.refresh(user)

        log_audit(
            user_id=actor.get("id", 0) if actor else 0,
            username=actor.get("username", "system") if actor else "system",
            action="update",
            target_user=user.username,
            details=f"fields={', '.join(k for k in updates if updates[k] is not None)}",
        )

        return {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "department": user.department,
            "position": user.position,
            "is_active": user.is_active,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update employee {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update employee")
    finally:
        db.close()


def change_employee_password(
    user_id: int, new_password: str, actor: dict | None = None
) -> dict:
    """เปลี่ยนรหัสผ่านพนักงาน"""
    validate_password_complexity(new_password)

    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้ที่ระบุ")

        user.password_hash = pwd_context.hash(new_password)
        db.commit()

        log_audit(
            user_id=actor.get("id", 0) if actor else 0,
            username=actor.get("username", "system") if actor else "system",
            action="change_password",
            target_user=user.username,
        )

        return {
            "status": "success",
            "message": f"เปลี่ยนรหัสผ่านสำหรับ {user.username} เรียบร้อยแล้ว",
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to change password for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to change password")
    finally:
        db.close()


def toggle_employee_active(user_id: int, actor: dict | None = None) -> dict:
    """เปิด/ปิดการใช้งานพนักงาน — ห้ามปิดตัวเอง"""
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้ที่ระบุ")

        # ห้ามปิดใช้งานตัวเอง
        if actor and actor.get("id") == user.id:
            raise HTTPException(
                status_code=400, detail="ไม่สามารถปิดการใช้งานบัญชีของตัวเองได้"
            )

        user.is_active = not user.is_active
        db.commit()

        action = "deactivate" if not user.is_active else "activate"
        log_audit(
            user_id=actor.get("id", 0) if actor else 0,
            username=actor.get("username", "system") if actor else "system",
            action=action,
            target_user=user.username,
        )

        return {
            "id": user.id,
            "username": user.username,
            "is_active": user.is_active,
            "message": f"{'เปิด' if user.is_active else 'ปิด'}การใช้งาน {user.username} เรียบร้อยแล้ว",
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to toggle active for user {user_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to toggle user active state"
        )
    finally:
        db.close()


def get_employee(user_id: int) -> dict:
    """ดึงข้อมูลพนักงานคนเดียว (ไม่รวม password hash)"""
    db = SessionLocal()
    try:
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้ที่ระบุ")
        return {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "name": user.name,
            "email": user.email,
            "phone": user.phone,
            "department": user.department,
            "position": user.position,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "updated_at": user.updated_at.isoformat() if user.updated_at else None,
        }
    finally:
        db.close()


def list_employees(
    page: int = 1,
    page_size: int = 20,
    search: str = "",
    role: str = "",
    active: bool | None = None,
) -> dict:
    """ดึงรายชื่อพนักงานแบบแบ่งหน้า + กรอง/ค้นหา"""
    db = SessionLocal()
    try:
        query = db.query(UserModel)

        if search:
            like = f"%{search}%"
            query = query.filter(
                (UserModel.username.ilike(like))
                | (UserModel.name.ilike(like))
                | (UserModel.email.ilike(like))
                | (UserModel.department.ilike(like))
                | (UserModel.position.ilike(like))
            )

        if role:
            query = query.filter(UserModel.role == role)

        if active is not None:
            query = query.filter(UserModel.is_active == active)

        total = query.count()
        pages = max(1, (total + page_size - 1) // page_size)
        page = max(1, min(page, pages))

        rows = (
            query.order_by(UserModel.username)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        employees = [
            {
                "id": u.id,
                "username": u.username,
                "role": u.role,
                "name": u.name,
                "email": u.email,
                "phone": u.phone,
                "department": u.department,
                "position": u.position,
                "is_active": u.is_active,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            }
            for u in rows
        ]

        return {
            "employees": employees,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": pages,
        }
    finally:
        db.close()


def get_audit_logs(page: int = 1, limit: int = 50, username: str = "") -> dict:
    """ดึงประวัติ audit logs"""
    db = SessionLocal()
    try:
        query = db.query(AuditLog)
        if username:
            query = query.filter(AuditLog.target_user.ilike(f"%{username}%"))

        total = query.count()
        pages = max(1, (total + limit - 1) // limit)
        page = max(1, min(page, pages))

        rows = (
            query.order_by(AuditLog.timestamp.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .all()
        )

        logs = [
            {
                "id": log.id,
                "user_id": log.user_id,
                "username": log.username,
                "action": log.action,
                "target_user": log.target_user,
                "details": log.details,
                "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            }
            for log in rows
        ]

        return {"logs": logs, "total": total, "page": page, "pages": pages}
    finally:
        db.close()
