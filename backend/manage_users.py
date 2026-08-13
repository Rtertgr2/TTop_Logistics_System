"""
CLI สำหรับจัดการผู้ใช้ระบบ (ใช้งานบน production server)

ตัวอย่าง:
    python manage_users.py create --username admin --role admin --name "Administrator"
    (ระบบจะถามรหัสผ่านจาก stdin — ไม่แสดงบนหน้าจอ)

    python manage_users.py list
    python manage_users.py deactivate --username some_user
    python manage_users.py activate --username some_user
"""

import argparse
import getpass
import sys


def _init_db():
    from database.db import init_db
    init_db()


def cmd_create(args):
    from fastapi import HTTPException
    from auth import create_user
    password = getpass.getpass("Password: ")
    if not password:
        print("❌ Password cannot be empty")
        sys.exit(1)
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("❌ Passwords do not match")
        sys.exit(1)
    try:
        user = create_user(
            args.username, password, role=args.role, name=args.name,
            email=args.email, phone=args.phone,
            department=args.department, position=args.position,
        )
        print(f"✅ สร้างผู้ใช้สำเร็จ: {user['username']} (role={user['role']}, name={user['name']})")
    except HTTPException as e:
        print(f"❌ {e.detail}")
        sys.exit(1)


def cmd_list(_args):
    from auth import list_users_from_db
    users = list_users_from_db()
    if not users:
        print("ไม่มีผู้ใช้ในฐานข้อมูล")
        return
    print(f"{'username':<20} {'role':<12} {'name':<30} {'active'}")
    print("-" * 70)
    for u in users:
        print(f"{u['username']:<20} {u['role']:<12} {u['name']:<30} {u['is_active']}")


def cmd_set_active(args, active: bool):
    from database.models import User as UserModel
    from database.db import SessionLocal
    db = SessionLocal()
    try:
        row = db.query(UserModel).filter(UserModel.username == args.username).first()
        if not row:
            print(f"❌ ไม่พบผู้ใช้: {args.username}")
            sys.exit(1)
        row.is_active = active
        db.commit()
        action = "เปิดใช้งาน" if active else "ปิดใช้งาน"
        print(f"✅ {action} ผู้ใช้: {args.username}")
    finally:
        db.close()


def cmd_deactivate(args):
    cmd_set_active(args, False)


def cmd_activate(args):
    cmd_set_active(args, True)


def main():
    parser = argparse.ArgumentParser(description="จัดการผู้ใช้ระบบ Logistics")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="สร้างผู้ใช้ใหม่")
    p_create.add_argument("--username", required=True)
    p_create.add_argument("--role", default="user", choices=["admin", "dispatcher", "driver", "user"])
    p_create.add_argument("--name", default="")
    p_create.add_argument("--email", default="")
    p_create.add_argument("--phone", default="")
    p_create.add_argument("--department", default="")
    p_create.add_argument("--position", default="")
    p_create.set_defaults(func=cmd_create)

    sub.add_parser("list", help="แสดงรายชื่อผู้ใช้").set_defaults(func=cmd_list)

    p_deact = sub.add_parser("deactivate", help="ปิดใช้งานผู้ใช้")
    p_deact.add_argument("--username", required=True)
    p_deact.set_defaults(func=cmd_deactivate)

    p_act = sub.add_parser("activate", help="เปิดใช้งานผู้ใช้")
    p_act.add_argument("--username", required=True)
    p_act.set_defaults(func=cmd_activate)

    args = parser.parse_args()
    _init_db()
    args.func(args)


if __name__ == "__main__":
    main()
