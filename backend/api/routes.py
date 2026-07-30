import json
import os
import logging
import urllib.parse
import requests
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional, Union, Any

from services.pdf_extractor import extract_pdf
from services.data_validator import validate_orders
from services.geocoding import geocode_orders, reverse_geocode, get_google_maps_api_key
from services.distance_matrix import get_distance_matrix
from services.route_optimizer import optimize_routes, load_vehicles
from services.excel_exporter import generate_all_routes_manifest_excel
from services.email_sender import send_route_email
from database.db import save_orders, save_route_plan, get_all_orders, get_route_history, clear_all_data, update_order_location, get_all_customer_locations, delete_customer_location, get_today_orders, get_today_active_routes, save_vehicles_to_db, get_vehicles_from_db, delete_vehicle_from_db
from config import DEPOT_LAT, DEPOT_LNG, DEPOT_ADDRESS, GOOGLE_MAPS_API_KEY, ENABLE_AI_REFINEMENT

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request/Response Models ──────────────────────────────────────

class PlanRoutesRequest(BaseModel):
    orders: list[dict]
    depot_address: Optional[str] = None
    depot_lat: Optional[float] = None
    depot_lng: Optional[float] = None


class SendEmailRequest(BaseModel):
    routes: list[dict]
    recipient: str


class VerifyLocationRequest(BaseModel):
    lat: float
    lng: float
    verified_by: Optional[str] = "user"


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/reverse-geocode")
async def get_reverse_geocode(lat: float, lng: float):
    """Reverse Geocoding: แปลงพิกัด lat/lng กลับเป็นที่อยู่"""
    addr = reverse_geocode(lat, lng)
    return {"formatted_address": addr, "lat": lat, "lng": lng}


@router.post("/orders/{order_id}/verify-location")
async def verify_order_location(order_id: int, req: VerifyLocationRequest):
    """ยืนยัน/แก้ไขตำแหน่งพิกัดออเดอร์โดยผู้ใช้งานหรือคนขับรถ"""
    success = update_order_location(order_id, req.lat, req.lng, req.verified_by or "user")
    if not success:
        raise HTTPException(status_code=404, detail="ไม่พบออเดอร์ดังกล่าวในฐานข้อมูล")
    return {"status": "success", "message": f"ยืนยันตำแหน่ง Order #{order_id} สำเร็จ", "lat": req.lat, "lng": req.lng}

@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...), use_ai: bool = Form(True)):
    """อัปโหลดไฟล์ PDF ไฟล์เดียว"""
    _validate_file(file)
    content = await file.read()
    orders = extract_pdf(content, file.filename, use_ai=use_ai)
    validated = validate_orders(orders)
    geocoded = geocode_orders(validated)
    save_orders(geocoded)
    return {"orders": geocoded}


@router.post("/upload-multiple")
async def upload_multiple_files(files: list[UploadFile] = File(...), use_ai: bool = Form(True)):
    """อัปโหลดไฟล์ PDF หลายไฟล์"""
    all_orders = []
    debug_info = []
    errors = []

    for file in files:
        try:
            _validate_file(file)
            content = await file.read()
            orders = extract_pdf(content, file.filename, use_ai=use_ai)
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
            errors.append({"filename": file.filename, "error": str(e)})
            logger.error(f"Error processing {file.filename}: {e}")

    # Validate and geocode all orders
    validated = validate_orders(all_orders)
    geocoded = geocode_orders(validated)

    # Save to Database
    save_orders(geocoded)

    logger.info(f"Total orders: {len(geocoded)}")
    return {
        "total_files": len(files),
        "total_orders": len(geocoded),
        "orders": geocoded,
        "debug": debug_info,
        "errors": errors,
    }


@router.post("/plan-routes")
async def plan_routes(request: PlanRoutesRequest):
    """คำนวณเส้นทางจัดส่ง"""
    orders = request.orders
    if not orders:
        raise HTTPException(status_code=400, detail="ไม่มีรายการสั่งซื้อ")

    # Depot
    depot = {
        "lat": request.depot_lat or DEPOT_LAT,
        "lng": request.depot_lng or DEPOT_LNG,
        "address": request.depot_address or DEPOT_ADDRESS,
    }

    try:
        # Re-geocode all orders with high-precision Google Maps Engine
        orders = geocode_orders(orders, force_refresh=True)

        # สร้าง distance matrix (depot เป็นจุดที่ 0)
        distance_matrix = get_distance_matrix(orders, depot)

        # โหลดข้อมูลรถ
        vehicles = load_vehicles()

        # Optimize routes
        routes = optimize_routes(orders, distance_matrix, vehicles, depot)

        # Save route plan to Database
        plan_id = save_route_plan(routes, depot)

        return {
            "plan_id": plan_id,
            "routes": routes,
            "total_orders": len(orders),
            "total_vehicles": len(routes),
            "depot": depot,
        }

    except Exception as e:
        logger.error(f"Route planning error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"เกิดข้อผิดพลาดในการคำนวณเส้นทาง: {str(e)}")


@router.get("/history")
async def get_history(limit: int = 20):
    """ดึงประวัติการประมวลผลจัดคิวรถย้อนหลัง จาก Database"""
    history = get_route_history(limit)
    return {"history": history, "total": len(history)}


@router.get("/orders/today")
async def get_today_orders_api():
    """ดึงรายการออเดอร์เฉพาะวันปัจจุบัน (ตัดรอบเที่ยงคืน)"""
    orders = get_today_orders()
    return {"orders": orders, "total": len(orders)}


@router.get("/routes/today")
async def get_today_routes_api():
    """ดึงแผนเส้นทางจัดคิวรถล่าสุดเฉพาะวันปัจจุบัน (ตัดรอบเที่ยงคืน)"""
    routes = get_today_active_routes()
    return {"routes": routes, "total": len(routes)}


@router.get("/orders-history")
async def get_orders_history(limit: int = 100):
    """ดึงออเดอร์ทั้งหมดที่เคยบันทึกใน Database"""
    orders = get_all_orders(limit)
    return {"orders": orders, "total": len(orders)}


@router.get("/customer-locations")
async def get_customer_locations(limit: int = 200):
    """ดึงข้อมูลคลังความจำพิกัดถาวรของลูกค้าทั้งหมด"""
    locations = get_all_customer_locations(limit)
    return {"locations": locations, "total": len(locations)}


@router.delete("/customer-locations/{loc_id}")
async def remove_customer_location(loc_id: int):
    """ลบพิกัดความจำถาวรของลูกค้าตาม ID"""
    success = delete_customer_location(loc_id)
    if not success:
        raise HTTPException(status_code=404, detail="ไม่พบรายการดังกล่าวใน Database")
    return {"status": "success", "message": "ลบรายการความจำเรียบร้อยแล้ว"}


@router.post("/send-email")
async def send_email(request: SendEmailRequest):
    """ส่งแผนเส้นทางทาง email"""
    if not request.recipient:
        raise HTTPException(status_code=400, detail="กรุณาระบุอีเมลผู้รับ")

    result = send_route_email(request.routes, request.recipient)

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result.get("message", "ส่ง email ไม่สำเร็จ"))

    return result


@router.get("/vehicles")
async def get_vehicles():
    """ดึงข้อมูลรถทั้งหมดจาก SQLite Database (รวมคันที่เปิดและปิดใช้งาน)"""
    try:
        vehicles = get_vehicles_from_db()
        return {"vehicles": vehicles}
    except Exception as e:
        logger.error(f"Error loading vehicles from DB: {e}")
        raise HTTPException(status_code=500, detail="ไม่สามารถโหลดข้อมูลรถจาก Database ได้")



@router.get("/search-place")
@router.get("/search-location")
async def search_place(address: str = None, q: str = None):
    """ค้นหาสถานที่จริงและพิกัดบนแผนที่ผ่าน Google Places API & Esri Engine"""
    query = address or q
    if not query or len(query.strip()) < 2:
        return {"results": []}

    clean_q = query.replace('ถ.', 'ถนน ').replace('ซ.', 'ซอย ').replace('จ.', 'จังหวัด ')
    google_key = get_google_maps_api_key()
    results = []

    # 1. 🌟 Google Places Text Search (High Precision POI Search)
    if google_key and not google_key.startswith("YOUR_"):
        try:
            places_url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={urllib.parse.quote(clean_q)}&key={google_key}&language=th&region=th"
            res = requests.get(places_url, timeout=3.0)
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
            logger.warning(f"Google Places search endpoint error: {e}")

    # 2. 📍 Esri World Geocoding Fallback
    try:
        url = f'https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?f=json&singleLine={urllib.parse.quote(clean_q + " Thailand")}&outFields=Match_addr,Addr_type&maxLocations=5'
        res = requests.get(url, timeout=3.0)
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
async def update_vehicles_config(payload: Union[list[dict], dict] = Body(...)):
    """บันทึก/อัปเดตข้อมูลรถ ทะเบียน คนขับ และความจุบรรทุก ลงใน SQLite Database"""
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
        raise HTTPException(status_code=500, detail=f"ไม่สามารถบันทึกข้อมูลรถลงใน Database: {str(e)}")


@router.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(vehicle_id: int):
    """ลบรถขนส่งคันที่ระบุออกจาก SQLite Database"""
    try:
        delete_vehicle_from_db(vehicle_id)
        return {"status": "success", "vehicles": get_vehicles_from_db()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ไม่สามารถลบรถใน Database: {e}")


@router.post("/export-manifest-excel")
async def export_manifest_excel(payload: dict):
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
async def get_system_status():
    """ดึงสถานะ API Key, AI Layer และฐานข้อมูล"""
    has_google_key = bool(GOOGLE_MAPS_API_KEY and not GOOGLE_MAPS_API_KEY.startswith("YOUR_"))
    db_orders = len(get_all_orders())
    return {
        "google_maps_api": "active" if has_google_key else "fallback",
        "ai_refinement": "active" if ENABLE_AI_REFINEMENT else "disabled",
        "total_orders_in_db": db_orders
    }


@router.post("/clear-data")
async def clear_system_data():
    """ล้างข้อมูลออเดอร์ แผนจัดส่ง และรีเซ็ตข้อมูล Fleet ในระบบทั้งหมด"""
    try:
        clear_all_data()
        
        # Reset vehicles.json to default 4 fleet vehicles
        v_file = os.path.join(os.path.dirname(__file__), "..", "data", "vehicles.json")
        default_vehicles = [
            {"id": 1, "name": "รถคันที่ 1 (รถใหญ่ 3.75 ตัน)", "plate": "กข 1234", "capacity": 3750, "driver": "สมชาย", "active": True},
            {"id": 2, "name": "รถคันที่ 2 (รถกลาง 1.8 - 1.9 ตัน)", "plate": "กข 5678", "capacity": 1900, "driver": "สมศักดิ์", "active": True},
            {"id": 3, "name": "รถคันที่ 3 (รถกลาง 1.95 - 2.24 ตัน)", "plate": "กข 9012", "capacity": 2240, "driver": "สมบูรณ์", "active": True},
            {"id": 4, "name": "รถคันที่ 4 (รถใหญ่ 3.75 ตัน)", "plate": "กข 3456", "capacity": 3750, "driver": "สมเดช", "active": True}
        ]
        with open(v_file, "w", encoding="utf-8") as f:
            json.dump(default_vehicles, f, ensure_ascii=False, indent=4)

        return {"status": "success", "message": "ล้างข้อมูลทั้งหมดในระบบเรียบร้อยแล้ว"}
    except Exception as e:
        logger.error(f"Error clearing data: {e}")
        raise HTTPException(status_code=500, detail=f"ไม่สามารถล้างข้อมูล: {e}")



# ── Helpers ──────────────────────────────────────────────────────

def _validate_file(file: UploadFile):
    """ตรวจสอบไฟล์ที่อัปโหลด"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="ไม่มีชื่อไฟล์")

    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail=f"รองรับเฉพาะไฟล์ PDF (ได้รับ: {file.filename})")

    # ตรวจ content type
    if file.content_type and file.content_type != "application/pdf":
        logger.warning(f"File {file.filename} has content_type: {file.content_type}")
