import os
import logging
import urllib.parse
import requests as http_requests
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, HTTPException, Body, Depends, Request, Query
from fastapi.responses import Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from typing import Optional, Union
from sqlalchemy import text

from services.pdf_extractor import extract_pdf
from services.data_validator import validate_orders
from services.geocoding import geocode_orders, reverse_geocode, get_google_maps_api_key
from services.route_optimizer import optimize_routes, load_vehicles
from services.excel_exporter import generate_all_routes_manifest_excel
from services.line_notifier import send_route_notification, send_driver_notification
from database.db import save_orders, save_route_plan, get_all_orders, get_route_history, clear_all_data, update_order_location, get_all_customer_locations, delete_customer_location, get_today_orders, get_today_active_routes, save_vehicles_to_db, get_vehicles_from_db, delete_vehicle_from_db, update_stop_status, auto_arrive_stop, get_stop_status_history, get_delivery_dashboard, get_driver_route, get_route_driver_name, update_item_delivery, reschedule_stop
from database.pdpa import export_user_personal_data, delete_user_personal_data, purge_expired_customer_data
from services.delivery_status import get_valid_next_statuses, get_status_label, get_status_color, calculate_delivery_summary
from services.load_balancer import detect_imbalances, find_transfer_suggestions, execute_transfer, recalculate_route_after_transfer, calculate_utilization
from services.road_snapping import snap_nearest_roads
from services.notifications import get_notifications, mark_notification_read, mark_all_read, get_unread_count, add_notification
from config import DATA_RETENTION_DAYS, PRIVACY_POLICY_VERSION, DPO_CONTACT_EMAIL
from config import DEPOT_LAT, DEPOT_LNG, DEPOT_ADDRESS, GOOGLE_MAPS_API_KEY, MAX_FILE_SIZE_MB, MAX_PDF_PAGES
from auth import login_user, get_current_user, require_role, list_users_from_db
from metrics import record_route_planned, record_order_processed


def _optional_user(request: Request):
    """Get current user if authenticated, None otherwise (non-blocking)"""
    try:
        return get_current_user(request)
    except HTTPException as e:
        if e.status_code in (401, 403):
            return None
        raise

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")


# ── Request/Response Models ──────────────────────────────────────

class PlanRoutesRequest(BaseModel):
    orders: list[dict] = Field(..., max_length=1000)
    depot_address: Optional[str] = None
    depot_lat: Optional[float] = None
    depot_lng: Optional[float] = None


class VerifyLocationRequest(BaseModel):
    lat: float
    lng: float
    verified_by: Optional[str] = "user"


class AssignDateRequest(BaseModel):
    order_ids: list[int]
    delivery_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")


class LoginRequest(BaseModel):
    username: str
    password: str


# ── Auth Endpoints ────────────────────────────────────────────────

@router.post("/auth/login")
def login(request: LoginRequest):
    """Login ด้วย username/password เพื่อรับ JWT token"""
    result = login_user(request.username, request.password)
    return result


@router.get("/auth/me")
def get_me(user: dict = Depends(get_current_user)):
    """ดึงข้อมูลผู้ใช้ปัจจุบันจาก JWT token"""
    return {"user": user}


@router.post("/auth/logout")
def logout(request: Request, user: dict = Depends(get_current_user)):
    """เพิกถอน JWT token ปัจจุบัน (logout)"""
    from auth import revoke_token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        revoke_token(auth_header[7:])
    return {"status": "ok", "message": "Logged out"}


# ── PDPA / GDPR Compliance Endpoints ────────────────────────────────

@router.get("/auth/export-data")
def export_my_data(user: dict = Depends(get_current_user)):
    """DSAR: ส่งออกข้อมูลส่วนบุคคลทั้งหมดที่ระบบเก็บของผู้ใช้คนนี้"""
    from database.db import SessionLocal
    from database.models import User as UserModel
    db = SessionLocal()
    try:
        row = db.query(UserModel).filter(UserModel.username == user["username"]).first()
        if not row:
            raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้")
        data = export_user_personal_data(row.id)
        if data is None:
            raise HTTPException(status_code=404, detail="ไม่พบข้อมูล")
        return {"data": data}
    finally:
        db.close()


@router.delete("/auth/delete-data")
def delete_my_data(user: dict = Depends(get_current_user)):
    """Right to erasure: ลบ/ทำลบข้อมูลส่วนบุคคลของผู้ใช้คนนี้ (ตามคำขอ)"""
    from database.db import SessionLocal
    from database.models import User as UserModel
    db = SessionLocal()
    try:
        row = db.query(UserModel).filter(UserModel.username == user["username"]).first()
        if not row:
            raise HTTPException(status_code=404, detail="ไม่พบผู้ใช้")
        ok = delete_user_personal_data(row.id)
        if not ok:
            raise HTTPException(status_code=500, detail="ไม่สามารถลบข้อมูลได้")
        return {"status": "ok", "message": "ข้อมูลส่วนบุคคลของคุณถูกลบเรียบร้อยแล้ว"}
    finally:
        db.close()


@router.get("/privacy-policy")
def privacy_policy():
    """เปิดเผยนโยบายความเป็นส่วนตัว + ช่องทางติดต่อ DPO (PDPA transparency)"""
    return {
        "policy_version": PRIVACY_POLICY_VERSION,
        "data_retention_days": DATA_RETENTION_DAYS,
        "dpo_contact_email": DPO_CONTACT_EMAIL,
        "data_subject_rights": [
            "right_of_access",
            "right_to_rectification",
            "right_to_erasure",
            "right_to_restrict_processing",
        ],
    }


@router.post("/admin/purge-data")
def admin_purge_data(
    retention_days: int = Query(DATA_RETENTION_DAYS, ge=1, le=3650),
    user: dict = Depends(require_role(["admin"])),
):
    """Admin: ลบข้อมูลออเดอร์ลูกค้าที่เก่ากว่ากำหนดตามนโยบายการเก็บรักษาข้อมูล (PDPA retention)"""
    result = purge_expired_customer_data(retention_days)
    return {"status": "ok", "result": result}


@router.get("/auth/users")
def list_users(user: dict = Depends(require_role(["admin"]))):
    """ดึงรายชื่อผู้ใช้ทั้งหมดจากฐานข้อมูล (admin only)"""
    users = list_users_from_db()
    return {"users": users}


# ── Employee Management Endpoints (RBAC: admin only) ──────────────

class CreateEmployeeRequest(BaseModel):
    username: str
    password: str
    role: str = "user"
    name: str = ""
    email: str = ""
    phone: str = ""
    department: str = ""
    position: str = ""
    consent_given: bool = False
    privacy_policy_version: str = ""


class UpdateEmployeeRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    role: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    new_password: str


@router.get("/auth/employees")
def get_employees(
    page: int = 1,
    page_size: int = Query(20, ge=1, le=500),
    search: str = "",
    role: str = "",
    active: Optional[bool] = None,
    user: dict = Depends(require_role(["admin"])),
):
    """ดึงรายชื่อพนักงานแบบแบ่งหน้า + กรอง/ค้นหา (admin only)"""
    from database.db import list_employees
    result = list_employees(page=page, page_size=page_size, search=search, role=role, active=active)
    return result


@router.get("/auth/employees/{user_id}")
def get_employee_by_id(user_id: int, user: dict = Depends(require_role(["admin"]))):
    """ดึงข้อมูลพนักงานคนเดียว (admin only)"""
    from database.db import get_employee
    return get_employee(user_id)


@router.post("/auth/employees")
def create_employee_endpoint(req: CreateEmployeeRequest, user: dict = Depends(require_role(["admin"]))):
    """สร้างพนักงานใหม่ (admin only)"""
    from database.db import create_employee
    return create_employee(
        username=req.username,
        password=req.password,
        role=req.role,
        name=req.name,
        email=req.email,
        phone=req.phone,
        department=req.department,
        position=req.position,
        actor=user,
        consent_given=req.consent_given,
        privacy_policy_version=req.privacy_policy_version,
    )


@router.put("/auth/employees/{user_id}")
def update_employee_endpoint(user_id: int, req: UpdateEmployeeRequest, user: dict = Depends(require_role(["admin"]))):
    """อัปเดตข้อมูลพนักงาน (admin only)"""
    from database.db import update_employee
    updates = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.email is not None:
        updates["email"] = req.email
    if req.phone is not None:
        updates["phone"] = req.phone
    if req.department is not None:
        updates["department"] = req.department
    if req.position is not None:
        updates["position"] = req.position
    if req.role is not None:
        updates["role"] = req.role
    return update_employee(user_id, updates, actor=user)


@router.put("/auth/employees/{user_id}/password")
def change_employee_password_endpoint(user_id: int, req: ChangePasswordRequest, user: dict = Depends(require_role(["admin"]))):
    """เปลี่ยนรหัสผ่านพนักงาน (admin only)"""
    from database.db import change_employee_password
    return change_employee_password(user_id, req.new_password, actor=user)


@router.put("/auth/employees/{user_id}/toggle-active")
def toggle_employee_active_endpoint(user_id: int, user: dict = Depends(require_role(["admin"]))):
    """เปิด/ปิดการใช้งานพนักงาน — ห้ามปิดตัวเอง (admin only)"""
    from database.db import toggle_employee_active
    return toggle_employee_active(user_id, actor=user)


@router.get("/auth/audit-logs")
def get_audit_logs_endpoint(
    page: int = 1,
    limit: int = Query(50, ge=1, le=500),
    username: str = "",
    user: dict = Depends(require_role(["admin"])),
):
    """ดึงประวัติ audit logs (admin only)"""
    from database.db import get_audit_logs
    return get_audit_logs(page=page, limit=limit, username=username)


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/reverse-geocode")
def get_reverse_geocode(lat: float, lng: float, user: dict = Depends(get_current_user)):
    """Reverse Geocoding: แปลงพิกัด lat/lng กลับเป็นที่อยู่"""
    addr = reverse_geocode(lat, lng)
    return {"formatted_address": addr, "lat": lat, "lng": lng}


@router.post("/orders/{order_id}/verify-location")
def verify_order_location(order: dict = Depends(require_role(["admin", "dispatcher"])), order_id: int = None, req: VerifyLocationRequest = None):
    """ยืนยัน/แก้ไขตำแหน่งพิกัดออเดอร์ (admin/dispatcher เท่านั้น)"""
    success = update_order_location(order_id, req.lat, req.lng, req.verified_by or "dispatcher")
    if not success:
        raise HTTPException(status_code=404, detail="ไม่พบออเดอร์ดังกล่าวในฐานข้อมูล")
    return {"status": "success", "message": f"ยืนยันตำแหน่ง Order #{order_id} สำเร็จ", "lat": req.lat, "lng": req.lng}

@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    """อัปโหลดไฟล์ PDF ไฟล์เดียว"""
    content = await _validate_file_content(file)
    orders = await run_in_threadpool(extract_pdf, content, file.filename)
    
    # ตรวจสอบว่ามี error จาก PDF parser (เช่น สินค้าไม่เจอใน Product table)
    if orders and orders[0].get("error"):
        error_data = orders[0]
        raise HTTPException(
            status_code=400,
            detail={
                "message": error_data["error"],
                "missing_products": error_data.get("missing_products", []),
                "customer": error_data.get("customer"),
                "order_number": error_data.get("order_number")
            }
        )
    
    validated = validate_orders(orders)
    geocoded = await run_in_threadpool(geocode_orders, validated)
    await run_in_threadpool(save_orders, geocoded)
    record_order_processed("success")
    return {"orders": geocoded}


@router.post("/upload-multiple")
async def upload_multiple_files(files: list[UploadFile] = File(...), user: dict = Depends(get_current_user)):
    """อัปโหลดไฟล์ PDF หลายไฟล์"""
    all_orders = []
    debug_info = []
    errors = []

    for file in files:
        try:
            content = await _validate_file_content(file)
            orders = await run_in_threadpool(extract_pdf, content, file.filename)
            
            # ตรวจสอบว่ามี error จาก PDF parser (เช่น สินค้าไม่เจอใน Product table)
            if orders and orders[0].get("error"):
                error_data = orders[0]
                errors.append({
                    "filename": file.filename,
                    "error": error_data["error"],
                    "missing_products": error_data.get("missing_products", []),
                    "customer": error_data.get("customer"),
                    "order_number": error_data.get("order_number")
                })
                logger.warning(f"Skip file {file.filename}: {error_data['error']}")
                continue
            
            all_orders.extend(orders)
            debug_info.append({
                "filename": file.filename,
                "size": len(content),
                "orders_found": len(orders),
            })
            logger.info(f"File: {file.filename}, Size: {len(content)}, Orders: {len(orders)}")
        except HTTPException as e:
            errors.append({"filename": file.filename, "error": e.detail})
            logger.warning(f"Skip file {file.filename}: {e.detail}")
        except Exception as e:
            errors.append({"filename": file.filename, "error": "File processing failed"})
            logger.error(f"Error processing {file.filename}: {e}", exc_info=True)

    # Validate and geocode all orders
    validated = validate_orders(all_orders)
    geocoded = await run_in_threadpool(geocode_orders, validated)

    # Save to Database
    await run_in_threadpool(save_orders, geocoded)

    # Record metrics
    record_order_processed("success" if not errors else "partial")

    logger.info(f"Total orders: {len(geocoded)}")
    return {
        "total_files": len(files),
        "total_orders": len(geocoded),
        "orders": geocoded,
        "debug": debug_info,
        "errors": errors,
    }


@router.post("/plan-routes")
def plan_routes(request: PlanRoutesRequest, user: dict = Depends(get_current_user)):
    """คำนวณเส้นทางจัดส่ง"""
    orders = request.orders
    if not orders:
        raise HTTPException(status_code=400, detail="ไม่มีรายการสั่งซื้อ")

    # Depot
    depot = {
        "lat": request.depot_lat if request.depot_lat is not None else DEPOT_LAT,
        "lng": request.depot_lng if request.depot_lng is not None else DEPOT_LNG,
        "address": request.depot_address or DEPOT_ADDRESS,
    }

    try:
        # Re-geocode all orders with high-precision Google Maps Engine
        orders = geocode_orders(orders, force_refresh=True)

        # โหลดข้อมูลรถ
        vehicles = load_vehicles()

        # Optimize routes (distance matrix computed internally)
        result = optimize_routes(orders, vehicles=vehicles, depot=depot)
        routes = result["routes"]
        warnings = result.get("warnings", [])
        clustered = result.get("clustered", False)

        # Save route plan to Database
        plan_id = save_route_plan(routes, depot)

        # Record metrics
        record_route_planned()

        return {
            "plan_id": plan_id,
            "routes": routes,
            "total_orders": len(orders),
            "total_vehicles": len(routes),
            "depot": depot,
            "warnings": warnings,
            "clustered": clustered,
            "deferred_orders": result.get("deferred_orders", []),
            "deferred_weight": result.get("deferred_weight", 0),
            "deferred_count": result.get("deferred_count", 0),
        }

    except Exception as e:
        logger.error(f"Route planning error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="เกิดข้อผิดพลาดในการคำนวณเส้นทาง")


@router.post("/plan-routes/async")
def plan_routes_async(request: PlanRoutesRequest, user: dict = Depends(get_current_user)):
    """คำนวณเส้นทางจัดส่งแบบ async (ใช้ Celery Background Task)"""
    import uuid
    from tasks import optimize_routes_task
    from tasks import get_task_status as get_task_status_store

    orders = request.orders
    if not orders:
        raise HTTPException(status_code=400, detail="ไม่มีรายการสั่งซื้อ")

    depot = {
        "lat": request.depot_lat if request.depot_lat is not None else DEPOT_LAT,
        "lng": request.depot_lng if request.depot_lng is not None else DEPOT_LNG,
        "address": request.depot_address or DEPOT_ADDRESS,
    }

    task_id = str(uuid.uuid4())

    try:
        task = optimize_routes_task.delay(orders=orders, depot=depot, task_id=task_id)
        logger.info(f"Async route planning started: task_id={task_id}, celery_id={task.id}")

        return {
            "task_id": task_id,
            "celery_task_id": task.id,
            "status": "queued",
            "message": "Route optimization task started. Poll /tasks/{task_id} for status.",
        }

    except Exception as e:
        logger.error(f"Failed to enqueue route planning task: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Task queue unavailable. Use synchronous /plan-routes endpoint.")


@router.get("/tasks/{task_id}")
def get_task_status(task_id: str, user: dict = Depends(get_current_user)):
    """ดึงสถานะของ background task"""
    from tasks import get_task_status as get_task_status_store

    status_info = get_task_status_store(task_id)
    return status_info


@router.get("/tasks")
def list_active_tasks(user: dict = Depends(get_current_user)):
    """ดึงรายการ background tasks ทั้งหมด (last 100)"""
    from tasks import get_task_status as get_task_status_store

    # Note: listing all tasks from Redis requires scanning, which is expensive.
    # For now, return empty list — users should poll specific task IDs.
    return {"tasks": [], "total": 0, "note": "Poll specific task IDs via GET /tasks/{task_id}"}


@router.get("/history")
def get_history(    limit: int = Query(20, ge=1, le=500), user: dict = Depends(get_current_user)):
    """ดึงประวัติการประมวลผลจัดคิวรถย้อนหลัง จาก Database"""
    history = get_route_history(limit)
    return {"history": history, "total": len(history)}


@router.get("/orders/today")
def get_today_orders_api(user: dict = Depends(get_current_user)):
    """ดึงรายการออเดอร์เฉพาะวันปัจจุบัน (ตัดรอบเที่ยงคืน)"""
    orders = get_today_orders()
    return {"orders": orders, "total": len(orders)}


@router.post("/orders/assign-date")
def assign_delivery_date_api(body: AssignDateRequest, user: dict = Depends(get_current_user)):
    """มอบหมายวันจัดส่งให้กับออเดอร์ที่เลือก"""
    from database.connection import SessionLocal
    from database.models import Order

    if not body.order_ids:
        raise HTTPException(status_code=400, detail="ไม่มี order_ids")
    if not body.delivery_date:
        raise HTTPException(status_code=400, detail="ไม่มี delivery_date")

    # Validate delivery_date format (YYYY-MM-DD)
    import re
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", body.delivery_date):
        raise HTTPException(status_code=400, detail="รูปแบบวันที่ไม่ถูกต้อง (ต้องเป็น YYYY-MM-DD)")

    db = SessionLocal()
    try:
        updated = db.query(Order).filter(Order.id.in_(body.order_ids)).update(
            {Order.delivery_date: body.delivery_date},
            synchronize_session="fetch",
        )
        db.commit()
        return {"success": True, "updated": updated, "delivery_date": body.delivery_date}
    except Exception as e:
        db.rollback()
        logger.error(f"Error assigning delivery date: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="ไม่สามารถมอบหมายวันจัดส่งได้")
    finally:
        db.close()


@router.get("/routes/today")
def get_today_routes_api(user: dict = Depends(get_current_user)):
    """ดึงแผนเส้นทางจัดคิวรถล่าสุดเฉพาะวันปัจจุบัน (ตัดรอบเที่ยงคืน)"""
    routes = get_today_active_routes()
    return {"routes": routes, "total": len(routes)}


@router.get("/orders-history")
def get_orders_history(    limit: int = Query(100, ge=1, le=500), user: dict = Depends(get_current_user)):
    """ดึงออเดอร์ทั้งหมดที่เคยบันทึกใน Database"""
    orders = get_all_orders(limit)
    return {"orders": orders, "total": len(orders)}


@router.get("/customer-locations")
def get_customer_locations(    limit: int = Query(200, ge=1, le=500), user: dict = Depends(get_current_user)):
    """ดึงข้อมูลคลังความจำพิกัดถาวรของลูกค้าทั้งหมด"""
    locations = get_all_customer_locations(limit)
    return {"locations": locations, "total": len(locations)}


@router.delete("/customer-locations/{loc_id}")
def remove_customer_location(loc_id: int, user: dict = Depends(require_role(["admin", "dispatcher"]))):
    """ลบพิกัดความจำถาวรของลูกค้าตาม ID"""
    success = delete_customer_location(loc_id)
    if not success:
        raise HTTPException(status_code=404, detail="ไม่พบรายการดังกล่าวใน Database")
    return {"status": "success", "message": "ลบรายการความจำเรียบร้อยแล้ว"}


@router.get("/orders/low-confidence")
def get_low_confidence_orders(threshold: float = 70.0, user: dict = Depends(get_current_user)):
    """ดึงออเดอร์ที่ Confidence Score ต่ำกว่า threshold (ค่าเริ่มต้น 70%) — 1.2.6"""
    all_orders = get_all_orders(limit=500)
    low_conf = [o for o in all_orders if (o.get("confidence_score") or 0) < threshold]
    return {"orders": low_conf, "total": len(low_conf), "threshold": threshold}


@router.get("/vehicles")
def get_vehicles(user: dict = Depends(get_current_user)):
    """ดึงข้อมูลรถทั้งหมดจาก Database (รวมคันที่เปิดและปิดใช้งาน)"""
    try:
        vehicles = get_vehicles_from_db()
        return {"vehicles": vehicles}
    except Exception as e:
        logger.error(f"Error loading vehicles from DB: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="ไม่สามารถโหลดข้อมูลรถจาก Database ได้")



@router.get("/search-place")
@router.get("/search-location")
def search_place(address: str = None, q: str = None, user: dict = Depends(get_current_user)):
    """ค้นหาสถานที่จริงและพิกัดบนแผนที่ผ่าน Google Places API & Esri Engine"""
    query = address or q
    if not query or len(query.strip()) < 2:
        return {"results": []}

    clean_q = query.replace('ถ.', 'ถนน ').replace('ซ.', 'ซอย ').replace('จ.', 'จังหวัด ')
    google_key = get_google_maps_api_key()
    results = []

    # 1. Google Places Text Search (High Precision POI Search)
    if google_key and not google_key.startswith("YOUR_"):
        try:
            places_url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={urllib.parse.quote(clean_q)}&key={google_key}&language=th&region=th"
            res = http_requests.get(places_url, timeout=3.0)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "OK" and data.get("results"):
                    for item in data["results"][:5]:
                        loc = item["geometry"]["location"]
                        name = item.get("name", "")
                        fmt = item.get("formatted_address", clean_q)
                        disp = f"{name} ({fmt})" if name and name not in fmt else fmt
                        results.append({
                            "display_name": disp,
                            "lat": round(float(loc["lat"]), 6),
                            "lng": round(float(loc["lng"]), 6),
                            "provider": "google_places"
                        })
                    if results:
                        return {"results": results}
        except Exception as e:
            logger.warning(f"Google Places search error: {e}")

    # 2. Esri World Geocoding Fallback
    try:
        url = f'https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?f=json&singleLine={urllib.parse.quote(clean_q + " Thailand")}&outFields=Match_addr,Addr_type&maxLocations=5'
        res = http_requests.get(url, timeout=3.0)
        if res.status_code == 200:
            candidates = res.json().get('candidates', [])
            for cand in candidates:
                results.append({
                    "display_name": cand.get("address", clean_q),
                    "lat": round(float(cand["location"]["y"]), 6),
                    "lng": round(float(cand["location"]["x"]), 6),
                    "provider": "esri"
                })
            return {"results": results}
    except Exception as e:
        logger.error(f"Search location Esri fallback error: {e}")

    return {"results": []}



@router.put("/vehicles")
def update_vehicles_config(payload: Union[list[dict], dict] = Body(...), user: dict = Depends(require_role(["admin", "dispatcher"]))):
    """บันทึก/อัปเดตข้อมูลรถ ทะเบียน คนขับ และความจุบรรทุก ลงใน Database (admin/dispatcher)"""
    try:
        if isinstance(payload, dict):
            vehicles = payload.get("vehicles", [])
        elif isinstance(payload, list):
            vehicles = payload
        else:
            vehicles = []

        save_vehicles_to_db(vehicles)
        return {"status": "success", "vehicles": get_vehicles_from_db()}
    except Exception as e:
        logger.error(f"Error updating vehicles in DB: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="ไม่สามารถบันทึกข้อมูลรถได้ กรุณาลองใหม่")


@router.delete("/vehicles/{vehicle_id}")
def delete_vehicle(vehicle_id: int, user: dict = Depends(require_role(["admin"]))):
    """ลบรถขนส่งคันที่ระบุออกจาก Database (admin only)"""
    try:
        delete_vehicle_from_db(vehicle_id)
        return {"status": "success", "vehicles": get_vehicles_from_db()}
    except Exception as e:
        logger.error(f"Error deleting vehicle: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="ไม่สามารถลบรถได้ กรุณาลองใหม่")


@router.post("/export-manifest-excel")
def export_manifest_excel(payload: dict, user: dict = Depends(get_current_user)):
    """ส่งออกไฟล์ Excel ใบสั่งงานคนขับรถ (Driver Manifest) รวมทุกคัน"""
    routes = payload.get("routes", [])
    if not routes:
        raise HTTPException(status_code=400, detail="ไม่พบข้อมูลเส้นทางจัดส่ง")
    excel_bytes = generate_all_routes_manifest_excel(routes)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=driver_manifest_all.xlsx"}
    )


@router.get("/system-status")
def get_system_status(user: dict = Depends(get_current_user)):
    """ดึงสถานะ API Key และฐานข้อมูล"""
    has_google_key = bool(GOOGLE_MAPS_API_KEY and not GOOGLE_MAPS_API_KEY.startswith("YOUR_"))
    db_orders = len(get_all_orders())
    return {
        "google_maps_api": "active" if has_google_key else "fallback",
        "total_orders_in_db": db_orders
    }


@router.post("/clear-data")
def clear_system_data(payload: dict, user: dict = Depends(require_role(["admin"]))):
    """ล้างข้อมูลออเดอร์ แผนจัดส่ง และรีเซ็ตข้อมูล Fleet ในระบบทั้งหมด (admin only)"""
    # Require typed confirmation
    confirm = payload.get("confirm", "")
    if confirm != "CLEAR_ALL_DATA":
        raise HTTPException(
            status_code=400,
            detail='กรุณาส่ง {"confirm": "CLEAR_ALL_DATA"} เพื่อยืนยันการล้างข้อมูล'
        )
    try:
        clear_all_data()
        logger.warning(f"ALL DATA CLEARED by user: {user.get('username', 'unknown')}")
        return {"status": "success", "message": "ล้างข้อมูลทั้งหมดในระบบเรียบร้อยแล้ว"}
    except Exception as e:
        logger.error(f"Error clearing data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="ไม่สามารถล้างข้อมูลได้ กรุณาลองใหม่")


@router.post("/send-line-notification")
def send_line_notification(payload: dict, user: dict = Depends(require_role(["admin", "dispatcher"]))):
    """ส่ง LINE notification สรุปแผนเส้นทาง (admin/dispatcher)"""
    routes = payload.get("routes", [])
    user_id = payload.get("user_id")
    if not routes:
        raise HTTPException(status_code=400, detail="ไม่มีข้อมูลเส้นทาง")
    result = send_route_notification(routes, user_id)
    return result


@router.post("/send-driver-notification")
def send_driver_line_notification(payload: dict, user: dict = Depends(require_role(["admin", "dispatcher"]))):
    """ส่ง LINE notification ไปยังคนขับเฉพาะคัน (admin/dispatcher)"""
    route = payload.get("route", {})
    driver_line_user_id = payload.get("driver_line_user_id")
    if not route:
        raise HTTPException(status_code=400, detail="ไม่มีข้อมูลเส้นทาง")
    if not driver_line_user_id:
        raise HTTPException(status_code=400, detail="ไม่มี LINE User ID ของคนขับ")
    result = send_driver_notification(route, driver_line_user_id)
    return result


# ── Helpers ──────────────────────────────────────────────────────

def _validate_file(file: UploadFile):
    """ตรวจสอบไฟล์ที่อัปโหลด"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="ไม่มีชื่อไฟล์")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="รองรับเฉพาะไฟล์ PDF เท่านั้น")

    # ตรวจ content type
    if file.content_type and file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="รองรับเฉพาะไฟล์ PDF เท่านั้น")

    # ตรวจ file size (enforce MAX_FILE_SIZE_MB from config)
    if file.size and file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"ไฟล์เกินขนาดสูงสุด {MAX_FILE_SIZE_MB} MB"
        )


async def _validate_file_content(file: UploadFile) -> bytes:
    """อ่านไฟล์แบบ streaming (ไม่โหลดทั้งไฟล์เข้า RAM) + ตรวจ magic bytes + จำกัดขนาด/จำนวนหน้า"""
    _validate_file(file)

    # Read first 4 bytes for magic byte check
    header = await file.read(4)
    await file.seek(0)  # Reset to beginning

    # PDF magic bytes: %PDF
    if not header.startswith(b'%PDF'):
        raise HTTPException(status_code=400, detail="ไฟล์ไม่ใช่ PDF ที่ถูกต้อง")

    # Stream-read with hard size cap (ป้องกัน memory exhaustion DoS)
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    chunks = []
    total = 0
    CHUNK = 1024 * 1024  # 1 MB
    while True:
        chunk = await file.read(CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"ไฟล์เกินขนาดสูงสุด {MAX_FILE_SIZE_MB} MB"
            )
        chunks.append(chunk)

    content = b"".join(chunks)

    # จำกัดจำนวนหน้า PDF (ป้องกัน decompression-bomb / parse CPU DoS)
    try:
        import fitz
        doc = fitz.open(stream=content, filetype="pdf")
        page_count = doc.page_count
        doc.close()
        if page_count > MAX_PDF_PAGES:
            raise HTTPException(
                status_code=413,
                detail=f"PDF มี {page_count} หน้า เกินขีดจำกัด {MAX_PDF_PAGES} หน้า"
            )
    except HTTPException:
        raise
    except Exception:
        # ถ้าเปิด PDF ไม่ได้ (ไฟล์เสีย) ให้ปล่อยผ่านเพื่อให้ extract_pdf รายงานต่อ
        pass

    return content


# ── Delivery Status Endpoints ────────────────────────────────────

class UpdateStopStatusRequest(BaseModel):
    route_id: int
    stop_id: int
    status: str
    note: Optional[str] = ""
    order_id: Optional[int] = None


class UpdateItemDeliveryRequest(BaseModel):
    stop_id: int
    order_item_id: int
    delivered_qty: float
    status: Optional[str] = "delivered"
    note: Optional[str] = ""


class AutoArriveRequest(BaseModel):
    route_id: int
    stop_id: int
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)
    accuracy_m: float = Field(..., ge=0, le=1000)
    event_id: Optional[str] = Field(None, max_length=100)


class RoadPointRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class SnapToRoadRequest(BaseModel):
    points: list[RoadPointRequest] = Field(..., min_length=1, max_length=100)


class RescheduleRequest(BaseModel):
    route_id: int
    stop_id: int
    reason: Optional[str] = ""


@router.post("/delivery/update-status")
def delivery_update_status(req: UpdateStopStatusRequest, user: dict = Depends(get_current_user)):
    """อัปเดตสถานะจุดจอด (driver/dispatcher)"""
    # ตรวจสอบสิทธิ์: driver เปลี่ยนได้เฉพาะจุดจอดในเส้นทางของตัวเอง
    role = user.get("role", "user")
    if role == "driver":
        route_driver = get_route_driver_name(req.route_id)
        if route_driver not in (user.get("username"), user.get("name")):
            raise HTTPException(
                status_code=403,
                detail="ไม่มีสิทธิ์อัปเดตสถานะของเส้นทางนี้"
            )
    result = update_stop_status(
        route_id=req.route_id,
        stop_id=req.stop_id,
        new_status=req.status.upper(),
        updated_by=user.get("username", "driver"),
        note=req.note or "",
        order_id=req.order_id
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    # Fire notification for failed deliveries
    if req.status.upper() == "FAILED":
        from services.notifications import notify_delivery_failed
        notify_delivery_failed(
            customer=f"Order #{req.stop_id}",
            driver=user.get("username", "driver"),
            reason=req.note or "ไม่ระบุเหตุผล",
            route_id=req.route_id,
            stop_id=req.stop_id,
        )

    return result


@router.post("/delivery/auto-arrive")
def delivery_auto_arrive(req: AutoArriveRequest, user: dict = Depends(get_current_user)):
    """Automatically mark an in-transit stop as ARRIVED from driver GPS."""
    if user.get("role") == "driver":
        route_driver = get_route_driver_name(req.route_id)
        if route_driver not in (user.get("username"), user.get("name")):
            raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์อัปเดตสถานะของเส้นทางนี้")

    result = auto_arrive_stop(
        route_id=req.route_id,
        stop_id=req.stop_id,
        lat=req.lat,
        lng=req.lng,
        accuracy_m=req.accuracy_m,
        updated_by=user.get("username") or user.get("name") or "driver",
        event_id=req.event_id,
    )
    if not result.get("success"):
        error = result.get("error", "ไม่สามารถตรวจสอบการถึงจุดส่งได้")
        status_code = 404 if "ไม่พบ" in error else 400
        raise HTTPException(status_code=status_code, detail=error)
    return result


@router.post("/snap-to-road")
def snap_to_road_endpoint(req: SnapToRoadRequest, user: dict = Depends(get_current_user)):
    """Snap delivery coordinates to nearby roads without changing verified pins."""
    points = [{"lat": point.lat, "lng": point.lng} for point in req.points]
    return {"points": snap_nearest_roads(points, enabled=True)}


@router.get("/delivery/status-history/{route_id}")
def delivery_status_history(route_id: int, stop_id: int = None, user: dict = Depends(get_current_user)):
    """ดึงประวัติการเปลี่ยนสถานะของ stop"""
    history = get_stop_status_history(route_id, stop_id)
    return {"history": history, "total": len(history)}


@router.get("/delivery/dashboard")
def delivery_dashboard(user: dict = Depends(get_current_user)):
    """ดึงข้อมูล Dashboard สถานะการจัดส่งวันนี้"""
    dashboard = get_delivery_dashboard()
    return dashboard


@router.get("/delivery/driver/{driver_name}")
def driver_route(driver_name: str, user: dict = Depends(get_current_user)):
    """ดึงเส้นทางของคนขับวันนี้ (driver เห็นได้เฉพาะเส้นทางตัวเอง)"""
    role = user.get("role", "user")
    if role == "driver" and driver_name != user.get("username") and driver_name != user.get("name"):
        raise HTTPException(status_code=403, detail="ไม่มีสิทธิ์ดูเส้นทางของคนขับอื่น")
    route = get_driver_route(driver_name)
    if not route:
        raise HTTPException(status_code=404, detail="ไม่พบเส้นทางของคนขับวันนี้")
    return route


@router.get("/delivery/valid-transitions/{current_status}")
def valid_transitions(current_status: str, user: dict = Depends(get_current_user)):
    """ดึงสถานะถัดไปที่สามารถเปลี่ยนได้"""
    statuses = get_valid_next_statuses(current_status.upper())
    return {
        "current_status": current_status.upper(),
        "valid_next_statuses": statuses,
        "labels": {s: get_status_label(s) for s in statuses},
        "colors": {s: get_status_color(s) for s in statuses},
    }


@router.post("/delivery/update-item")
def delivery_update_item(req: UpdateItemDeliveryRequest, user: dict = Depends(require_role(["admin", "dispatcher"]))):
    """อัปเดตสถานะการจัดส่งระดับ item"""
    success = update_item_delivery(
        stop_id=req.stop_id,
        order_item_id=req.order_item_id,
        delivered_qty=req.delivered_qty,
        status=req.status,
        note=req.note or ""
    )
    if not success:
        raise HTTPException(status_code=500, detail="ไม่สามารถอัปเดตสถานะสินค้าได้")
    return {"success": True}


@router.post("/delivery/reschedule")
def delivery_reschedule(req: RescheduleRequest, user: dict = Depends(require_role(["admin", "dispatcher"]))):
    """เลื่อนการจัดส่ง (admin/dispatcher only)"""
    result = reschedule_stop(
        route_id=req.route_id,
        stop_id=req.stop_id,
        reason=req.reason or "เลื่อนจัดส่ง",
        updated_by=user.get("username", "dispatcher")
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    # Fire notification
    from services.notifications import notify_stop_rescheduled
    notify_stop_rescheduled(
        customer=f"Order #{req.stop_id}",
        reason=req.reason or "เลื่อนจัดส่ง",
        dispatcher=user.get("username", "dispatcher"),
    )

    return result


@router.get("/delivery/summary")
def delivery_summary(user: dict = Depends(get_current_user)):
    """ดึงสรุปสถานะการจัดส่งวันนี้"""
    dashboard = get_delivery_dashboard()
    if not dashboard.get("has_plan"):
        return {"has_plan": False, "summary": None}
    return {"has_plan": True, "summary": dashboard["summary"], "routes": dashboard["routes"]}


# ── Load Balancing Endpoints ─────────────────────────────────────

class ExecuteTransferRequest(BaseModel):
    source_route_id: int
    target_route_id: int
    stop_id: int


@router.get("/load-balance/analyze")
def load_balance_analyze(user: dict = Depends(get_current_user)):
    """วิเคราะห์สถานะรถทุกคัน — ตรวจจับ overflow/underflow"""
    routes = get_today_active_routes()
    if not routes:
        return {"has_routes": False, "message": "ยังไม่มีเส้นทางวันนี้"}

    imbalances = detect_imbalances(routes)
    return {
        "has_routes": True,
        "vehicles": imbalances["vehicles"],
        "overflow_count": len(imbalances["overflow"]),
        "underflow_count": len(imbalances["underflow"]),
        "needs_transfer": imbalances["needs_transfer"],
    }


@router.get("/load-balance/suggestions")
def load_balance_suggestions(user: dict = Depends(get_current_user)):
    """หาคำแนะนำการย้าย stop ระหว่างรถ"""
    routes = get_today_active_routes()
    if not routes:
        return {"has_routes": False, "suggestions": []}

    suggestions = find_transfer_suggestions(routes)
    return {
        "has_routes": True,
        "suggestions": suggestions,
        "total": len(suggestions),
    }


@router.post("/load-balance/execute")
def load_balance_execute(req: ExecuteTransferRequest, user: dict = Depends(require_role(["admin", "dispatcher"]))):
    """Execute transfer — ย้าย stop จาก source ไป target"""
    result = execute_transfer(
        source_route_id=req.source_route_id,
        target_route_id=req.target_route_id,
        stop_id=req.stop_id,
        approved_by=user.get("username", "dispatcher")
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])

    # Re-calculate route sequence
    recalculate_route_after_transfer(req.target_route_id)

    # Fire notification
    from services.notifications import notify_transfer_executed
    notify_transfer_executed(
        source_driver=f"Route #{req.source_route_id}",
        target_driver=f"Route #{req.target_route_id}",
        customer=f"Stop #{req.stop_id}",
        approved_by=user.get("username", "dispatcher"),
    )

    return result


@router.get("/load-balance/vehicle/{route_id}")
def load_balance_vehicle_detail(route_id: int, user: dict = Depends(get_current_user)):
    """ดึงรายละเอียด utilization ของรถคันเดียว"""
    routes = get_today_active_routes()
    if not routes:
        raise HTTPException(status_code=404, detail="ไม่พบเส้นทางวันนี้")

    for route in routes:
        if route.get("id") == route_id:
            util = calculate_utilization(route, route.get("capacity", 3750))
            return util

    raise HTTPException(status_code=404, detail="ไม่พบเส้นทาง")


@router.get("/load-balance/transfer-history")
def load_balance_transfer_history(user: dict = Depends(get_current_user)):
    """ดึงประวัติการย้าย stop วันนี้"""
    from database.db import SessionLocal
    from database.models import RouteTransfer

    db = SessionLocal()
    try:
        today = datetime.now(timezone.utc).date()
        transfers = db.query(RouteTransfer).filter(
            text("DATE(created_at AT TIME ZONE 'UTC') = :today")
        ).params(today=today).order_by(RouteTransfer.created_at.desc()).all()

        return {
            "transfers": [
                {
                    "id": t.id,
                    "stop_id": t.stop_id,
                    "order_id": t.order_id,
                    "from_route_id": t.from_route_id,
                    "to_route_id": t.to_route_id,
                    "from_vehicle_id": t.from_vehicle_id,
                    "to_vehicle_id": t.to_vehicle_id,
                    "transfer_type": t.transfer_type,
                    "reason": t.reason,
                    "approved_by": t.approved_by,
                    "created_at": t.created_at,
                }
                for t in transfers
            ],
            "total": len(transfers),
        }
    finally:
        db.close()


# ── Notification Endpoints ───────────────────────────────────────

@router.get("/notifications")
def list_notifications(unread: bool = False, limit: int = 50, user: dict = Depends(get_current_user)):
    """ดึง notifications"""
    role = user.get("role", "dispatcher")
    notifs = get_notifications(target_role=role, unread_only=unread, limit=limit)
    unread_count = get_unread_count(target_role=role)
    return {"notifications": notifs, "total": len(notifs), "unread_count": unread_count}


@router.get("/notifications/unread-count")
def notification_unread_count(user: dict = Depends(get_current_user)):
    """ดึงจำนวน unread notifications"""
    role = user.get("role", "dispatcher")
    count = get_unread_count(target_role=role)
    return {"unread_count": count}


@router.put("/notifications/{notification_id}/read")
def mark_read(notification_id: int, user: dict = Depends(get_current_user)):
    """ทำเครื่องหมาย notification เป็นอ่านแล้ว (เฉพาะ notification ของ role ตนเอง)"""
    success = mark_notification_read(notification_id, target_role=user.get("role"))
    if not success:
        raise HTTPException(status_code=404, detail="ไม่พบ notification ของสิทธิ์นี้")
    return {"success": success}


@router.put("/notifications/mark-all-read")
def mark_all_notifications_read(user: dict = Depends(get_current_user)):
    """ทำเครื่องหมายทั้งหมดเป็นอ่านแล้ว"""
    role = user.get("role", "dispatcher")
    count = mark_all_read(target_role=role)
    return {"marked_count": count}


# ── Booking Endpoints ────────────────────────────────────────────

class AssignBookingRequest(BaseModel):
    order_ids: list[int]
    delivery_date: str
    booking_status: Optional[str] = "booked"


@router.get("/booking/pending")
def get_booking_pending(user: dict = Depends(get_current_user)):
    """ดึงออเดอร์ที่ยังไม่ได้กำหนดวันส่ง (booking_status = pending หรือไม่มี delivery_date)"""
    from database.connection import SessionLocal
    from database.models import Order

    db = SessionLocal()
    try:
        orders = db.query(Order).filter(
            (Order.booking_status == "pending") | (Order.delivery_date.is_(None))
        ).order_by(Order.id.desc()).all()

        result = []
        for o in orders:
            result.append({
                "id": o.id,
                "order_number": o.order_number,
                "customer": o.customer,
                "address": o.address,
                "weight": o.weight,
                "lat": o.lat,
                "lng": o.lng,
                "booking_status": o.booking_status or "pending",
                "delivery_date": o.delivery_date,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            })
        return {"orders": result, "total": len(result)}
    finally:
        db.close()


@router.get("/booking/calendar")
def get_booking_calendar(user: dict = Depends(get_current_user)):
    """ดึงข้อมูลปฏิทินจองวันส่ง — กลุ่มออเดอร์ตาม delivery_date"""
    from database.connection import SessionLocal
    from database.models import Order

    db = SessionLocal()
    try:
        orders = db.query(Order).filter(
            Order.delivery_date.is_(None) == False
        ).order_by(Order.delivery_date.asc()).all()

        calendar = {}
        for o in orders:
            date = o.delivery_date
            if not date:
                continue
            if date not in calendar:
                calendar[date] = {"count": 0, "total_weight": 0, "orders": []}
            calendar[date]["count"] += 1
            calendar[date]["total_weight"] += float(o.weight or 0)
            calendar[date]["orders"].append({
                "id": o.id,
                "order_number": o.order_number,
                "customer": o.customer,
                "weight": o.weight,
            })
        return {"calendar": calendar}
    finally:
        db.close()


@router.post("/booking/assign")
def assign_booking(req: AssignBookingRequest, user: dict = Depends(require_role(["admin", "dispatcher"]))):
    """กำหนดวันส่งให้ออเดอร์ที่เลือก"""
    from database.connection import SessionLocal
    from database.models import Order

    db = SessionLocal()
    try:
        updated = 0
        for oid in req.order_ids:
            order = db.query(Order).filter(Order.id == oid).first()
            if order:
                order.delivery_date = req.delivery_date
                order.booking_status = req.booking_status or "booked"
                updated += 1

        db.commit()
        logger.info(f"Booking assigned: {updated} orders -> {req.delivery_date} by {user.get('username', 'unknown')}")
        return {"status": "success", "updated": updated, "delivery_date": req.delivery_date}
    except Exception as e:
        db.rollback()
        logger.error(f"Error assigning booking: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="ไม่สามารถกำหนดวันส่งได้")
    finally:
        db.close()
