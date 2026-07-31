import logging
import os
import re
import time
import hashlib
import json
import urllib.parse
import requests
from dotenv import load_dotenv
import config

logger = logging.getLogger(__name__)

# โหลด environment variables จากไฟล์ .env โดยตรง
load_dotenv()


_CACHED_API_KEY = None

def get_google_maps_api_key() -> str:
    """ดึง GOOGLE_MAPS_API_KEY โดยตรงจากไฟล์ .env หรือ os.getenv พร้อม Caching"""
    global _CACHED_API_KEY
    if _CACHED_API_KEY is not None:
        return _CACHED_API_KEY
    load_dotenv()
    key = os.getenv("GOOGLE_MAPS_API_KEY", "") or getattr(config, "GOOGLE_MAPS_API_KEY", "")
    _CACHED_API_KEY = key.strip()
    return _CACHED_API_KEY


LMSTUDIO_URL = getattr(config, "LMSTUDIO_URL", "http://localhost:1234/v1")
ENABLE_AI_REFINEMENT = getattr(config, "ENABLE_AI_REFINEMENT", True)

# Cache for online place searches to eliminate redundant network requests
GEOCODE_CACHE = {}

# Thailand Bounding Box (Lat 5.0N - 21.0N, Lon 97.0E - 106.0E)
THAILAND_BOUNDS = {
    "min_lat": 5.0,
    "max_lat": 21.0,
    "min_lng": 97.0,
    "max_lng": 106.0
}


def _request_with_retry(url: str, max_retries: int = 3, base_delay: float = 1.0, timeout: float = 3.0) -> requests.Response | None:
    """HTTP GET with exponential backoff retry (1.2.8)"""
    for attempt in range(max_retries):
        try:
            res = requests.get(url, timeout=timeout)
            if res.status_code == 429:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Rate limit hit (429), retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                continue
            if res.status_code == 200:
                return res
            logger.warning(f"HTTP {res.status_code} for {url[:80]}")
            return res
        except requests.exceptions.Timeout:
            delay = base_delay * (2 ** attempt)
            logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}, retrying in {delay}s")
            time.sleep(delay)
        except requests.exceptions.ConnectionError as e:
            delay = base_delay * (2 ** attempt)
            logger.warning(f"Connection error on attempt {attempt + 1}/{max_retries}: {e}")
            time.sleep(delay)
        except Exception as e:
            logger.error(f"Request error: {e}")
            return None

    logger.error(f"All {max_retries} retries exhausted for {url[:80]}")
    return None


def is_in_thailand(lat: float, lng: float) -> bool:
    """ตรวจสอบว่าพิกัดอยู่ในประเทศไทยจริงหรือไม่"""
    if lat is None or lng is None:
        return False
    return (THAILAND_BOUNDS["min_lat"] <= lat <= THAILAND_BOUNDS["max_lat"] and
            THAILAND_BOUNDS["min_lng"] <= lng <= THAILAND_BOUNDS["max_lng"])


def clean_customer_name(customer: str) -> str:
    """ตัดรหัสลูกค้านำหน้าออก เช่น 'ย101609ยีสต์ กะ เนย' => 'ยีสต์ กะ เนย' เพื่อให้ค้นพิกัดใน Google Maps เจอ"""
    if not customer:
        return ""
    # ตัดโค้ดรหัสนำหน้า เช่น ย101609, C00123, 101609
    clean = re.sub(r'^[ก-๙a-zA-Z]{1,3}\d{4,8}\s*', '', customer)
    clean = re.sub(r'^\d{4,8}\s*', '', clean)
    clean = re.sub(r'^\([^\)]+\)\s*', '', clean)
    return clean.strip()


def search_place_online(address: str) -> tuple[float, float, str, str, float] | None:
    """
    ค้นหาสถานที่จริงด้วย Multi-Provider Engine (Google Places POI / Google Geocoding / Esri / OpenStreetMap)
    Return: (lat, lng, formatted_address, provider, confidence_score)
    """
    if not address or len(address.strip()) < 2:
        return None

    if address in GEOCODE_CACHE:
        return GEOCODE_CACHE[address]

    # ทำความสะอาดที่อยู่ภาษาไทย
    clean = address.replace('ถ.', 'ถนน').replace('ซ.', 'ซอย ').replace('จ.', 'จังหวัด ')
    clean = clean.replace('อ.', 'อำเภอ ').replace('ต.', 'ตำบล ').replace('กทม', 'กรุงเทพมหานคร')
    clean = re.sub(r'[*\(\)\[\]]', '', clean)
    clean = re.sub(r'\s+', ' ', clean).strip()

    if len(clean) < 3:
        return None

    google_key = get_google_maps_api_key()

    # 0. 🌟 Google Places Text Search API (ค้นหาชื่อสถานที่/บริษัท/ร้านค้า POI จริง - 100% ROOFTOP)
    if google_key and not google_key.startswith("YOUR_"):
        try:
            places_url = f"https://maps.googleapis.com/maps/api/place/textsearch/json?query={urllib.parse.quote(clean)}&key={google_key}&language=th&region=th"
            res = _request_with_retry(places_url)
            if res and res.status_code == 200:
                data = res.json()
                if data.get("status") == "OK" and data.get("results"):
                    first = data["results"][0]
                    loc = first["geometry"]["location"]
                    lat = round(float(loc["lat"]), 6)
                    lng = round(float(loc["lng"]), 6)
                    name = first.get("name", "")
                    formatted = first.get("formatted_address", clean)
                    display_name = f"{name} ({formatted})" if name and name not in formatted else formatted
                    if is_in_thailand(lat, lng):
                        result = (lat, lng, display_name, "google_places", 100.0)
                        GEOCODE_CACHE[address] = result
                        logger.info(f"🌟 Google Places POI Match (Score=100%): '{clean[:50]}' => {lat}, {lng}")
                        return result
        except Exception as e:
            logger.warning(f"Google Places API error: {e}")

    # 1. 🎯 Google Maps Geocoding API (Precision Scoring ตาม Location Type จริง)
    if google_key and not google_key.startswith("YOUR_"):
        try:
            url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(clean)}&key={google_key}&components=country:TH"
            res = _request_with_retry(url)
            if res and res.status_code == 200:
                data = res.json()
                if data.get("status") == "OK" and data.get("results"):
                    first = data["results"][0]
                    loc = first["geometry"]["location"]
                    lat = round(float(loc["lat"]), 6)
                    lng = round(float(loc["lng"]), 6)
                    location_type = first.get("geometry", {}).get("location_type", "APPROXIMATE")
                    
                    # ⚠️ ตรวจสอบ Precision ให้ตรงความเป็นจริง (ROOFTOP=98%, RANGE_INTERPOLATED=85%, GEOMETRIC_CENTER=55%, APPROXIMATE=30%)
                    if location_type == "ROOFTOP":
                        score = 98.0
                    elif location_type == "RANGE_INTERPOLATED":
                        score = 85.0
                    elif location_type == "GEOMETRIC_CENTER":
                        score = 55.0  # จุดกึ่งกลางถนน/ซอย (ไม่ใช่หลังคาตึกจริง)
                    else:
                        score = 30.0  # จุดศูนย์กลางระดับตำบล/อำเภอ (คลาดเคลื่อนสูง)

                    if not is_in_thailand(lat, lng):
                        score = 0.0

                    formatted = first.get("formatted_address", clean)
                    result = (lat, lng, formatted, "google", score)
                    GEOCODE_CACHE[address] = result
                    logger.info(f"🎯 Google Maps Match ({location_type}, Score={score}%): '{clean[:50]}' => {lat}, {lng}")
                    return result
        except Exception as e:
            logger.warning(f"Google Maps geocoding error: {e}")

    # 2. 📍 Esri World Geocoding API (Fallback 1)
    try:
        query_str = clean + ' Thailand'
        url = f'https://geocode.arcgis.com/arcgis/rest/services/World/GeocodeServer/findAddressCandidates?f=json&singleLine={urllib.parse.quote(query_str)}&outFields=Match_addr,Score&maxLocations=1&countryCode=THA'
        res = _request_with_retry(url)
        if res and res.status_code == 200:
            data = res.json()
            candidates = data.get('candidates', [])
            if candidates:
                cand = candidates[0]
                esri_score = cand.get('attributes', {}).get('Score', 0)
                if esri_score >= 50:
                    loc = cand['location']
                    lat = round(float(loc['y']), 6)
                    lng = round(float(loc['x']), 6)
                    display_name = cand.get('address', '') or clean
                    score = float(min(round(esri_score * 0.75, 1), 75.0)) # ปรับคะแนนให้ตรงความจริง
                    if not is_in_thailand(lat, lng):
                        score = 0.0
                    result = (lat, lng, display_name, "esri", score)
                    GEOCODE_CACHE[address] = result
                    logger.info(f"📍 Esri Match (Score={score}%): '{clean[:50]}' => {lat}, {lng}")
                    return result
    except Exception as e:
        logger.warning(f"Esri geocoding error: {e}")

    # 3. 🗺️ OpenStreetMap Nominatim API (Fallback 2)
    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={urllib.parse.quote(clean)}&countrycodes=th&limit=1"
        headers = {'User-Agent': 'LogisticsRoutePlanner/1.0'}
        res = _request_with_retry(url)
        if res and res.status_code == 200:
            data = res.json()
            if data:
                lat = round(float(data[0]["lat"]), 6)
                lng = round(float(data[0]["lon"]), 6)
                display_name = data[0].get("display_name", clean)
                score = 60.0 if is_in_thailand(lat, lng) else 0.0
                result = (lat, lng, display_name, "nominatim", score)
                GEOCODE_CACHE[address] = result
                logger.info(f"🗺️ Nominatim Match: '{clean[:50]}' => {lat}, {lng}")
                return result
    except Exception as e:
        logger.warning(f"Nominatim geocoding error: {e}")

    return None


def reverse_geocode(lat: float, lng: float) -> str:
    """Reverse Geocoding: แปลงพิกัด lat/lng กลับเป็นข้อความที่อยู่จัดส่งจริง"""
    if not lat or not lng:
        return "ไม่ระบุพิกัด"

    google_key = get_google_maps_api_key()
    if google_key and not google_key.startswith("YOUR_"):
        try:
            url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lng}&key={google_key}&language=th"
            res = requests.get(url, timeout=3.0)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == "OK" and data.get("results"):
                    return data["results"][0].get("formatted_address", f"{lat:.6f}, {lng:.6f}")
        except Exception as e:
            logger.warning(f"Google Reverse Geocode error: {e}")

    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}&accept-language=th"
        headers = {'User-Agent': 'LogisticsRoutePlanner/1.0'}
        res = requests.get(url, headers=headers, timeout=3.0)
        if res.status_code == 200:
            data = res.json()
            if data and "display_name" in data:
                return data["display_name"]
    except Exception as e:
        logger.warning(f"Nominatim Reverse Geocode error: {e}")

    return f"พิกัด {lat:.6f}, {lng:.6f}"


def ai_classify_geographic_zone(address: str) -> dict:
    """AI Geographic Zone Intelligence Engine: จำแนกโซนด้วยระบบปัญญาประดิษฐ์"""
    if not address or len(address.strip()) < 2:
        return {
            "zone": "ไม่ระบุ",
            "province": "กรุงเทพฯ",
            "district": "ไม่ระบุ",
            "ai_confidence": 0.50
        }

    clean_addr = re.sub(r'[\r\n\t]', ' ', address).strip()

    prov = "กรุงเทพฯ"
    dist = "ไม่ระบุ"
    confidence = 0.95

    if any(k in clean_addr for k in ["นนทบุรี", "ปากเกร็ด", "บางบัวทอง", "บางใหญ่", "บางกรวย", "ไทรน้อย"]):
        prov = "นนทบุรี"
        if "บางบัวทอง" in clean_addr or "พิมลราช" in clean_addr:
            dist = "บางบัวทอง"
        elif "ปากเกร็ด" in clean_addr or "คลองพระอุดม" in clean_addr or "บางพูด" in clean_addr or "ชัยพฤกษ์" in clean_addr:
            dist = "ปากเกร็ด"
        elif "เมืองนนทบุรี" in clean_addr or "บางเขน" in clean_addr or "งามวงศ์วาน" in clean_addr or "บางไผ่" in clean_addr:
            dist = "เมืองนนทบุรี"
        else:
            dist = "เมืองนนทบุรี"
    elif any(k in clean_addr for k in ["ปทุมธานี", "คลองหลวง", "คลองหนึ่ง", "ธัญบุรี", "ลำลูกกา"]):
        prov = "ปทุมธานี"
        dist = "คลองหลวง" if ("คลองหลวง" in clean_addr or "คลองหนึ่ง" in clean_addr) else "เมืองปทุมธานี"
    elif any(k in clean_addr for k in ["สมุทรสาคร", "กระทุ่มแบน", "บ้านแพ้ว", "สุคนธวิท"]):
        prov = "สมุทรสาคร"
        dist = "กระทุ่มแบน" if ("กระทุ่มแบน" in clean_addr or "สุคนธวิท" in clean_addr) else "เมืองสมุทรสาคร"
    elif any(k in clean_addr for k in ["นครปฐม", "สามพราน", "ไร่ขิง", "ท่าตลาด", "พุทธมณฑล"]):
        prov = "นครปฐม"
        dist = "สามพราน"
    elif any(k in clean_addr for k in ["สุรินทร์", "จอมพระ"]):
        prov = "สุรินทร์"
        dist = "จอมพระ"
    else:
        # กรุงเทพมหานคร 50 เขต
        prov = "กรุงเทพฯ"
        if "พญาไท" in clean_addr or "สามเสนใน" in clean_addr:
            dist = "พญาไท"
        elif "จตุจักร" in clean_addr or "ลาดยาว" in clean_addr:
            dist = "จตุจักร"
        elif "พระนคร" in clean_addr or "บวรนิเวศ" in clean_addr or "ถ.ตะนาว" in clean_addr:
            dist = "พระนคร"
        elif "บางพลัด" in clean_addr or "สิรินธร" in clean_addr:
            dist = "บางพลัด"
        elif "หนองแขม" in clean_addr or "หนองค้างพลู" in clean_addr or "เพชรเกษม" in clean_addr:
            dist = "หนองแขม"
        elif "บางบอน" in clean_addr or "เอกชัย" in clean_addr:
            dist = "บางบอน"
        elif "วัฒนา" in clean_addr or "คลองตัน" in clean_addr or "สุขุมวิท" in clean_addr:
            dist = "วัฒนา"
        elif "สัมพันธวงศ์" in clean_addr or "จักรวรรดิ" in clean_addr or "จักรเพชร" in clean_addr:
            dist = "สัมพันธวงศ์"
        elif "คลองเตย" in clean_addr:
            dist = "คลองเตย"
        elif "บางนา" in clean_addr or "อุดมสุข" in clean_addr:
            dist = "บางนา"
        else:
            m_dist = re.search(r'(?:เขต|อำเภอ|อ\.)\s*([ก-๙a-zA-Z0-9\-]+)', clean_addr)
            dist = m_dist.group(1).strip() if m_dist else "ทั่วไป"

    zone_label = f"{prov} ({dist})"
    return {
        "zone": zone_label,
        "province": prov,
        "district": dist,
        "ai_confidence": confidence
    }


def geocode_address(address: str, customer: str = "") -> dict:
    """แปลงที่อยู่และชื่อบริษัท/ลูกค้าภาษาไทยเป็นพิกัดจริงด้วยระบบ Multi-Stage Precision Search Engine"""
    depot_lat_val = getattr(config, "DEPOT_LAT", 13.781882)
    depot_lng_val = getattr(config, "DEPOT_LNG", 100.425041)

    if not address or len(address.strip()) < 2:
        return {
            "lat": depot_lat_val,
            "lng": depot_lng_val,
            "raw_lat": depot_lat_val,
            "raw_lng": depot_lng_val,
            "verified_lat": depot_lat_val,
            "verified_lng": depot_lng_val,
            "formatted_address": address or "ไม่ระบุที่อยู่",
            "zone": "ไม่ระบุ",
            "geocode_provider": "none",
            "confidence_score": 0.0,
            "is_verified": False
        }

    clean_addr = re.sub(r'[\r\n\t]', ' ', address).strip()
    raw_cust = re.sub(r'[\r\n\t]', ' ', customer).strip() if customer else ""
    clean_cust = clean_customer_name(raw_cust)

    # 1. AI Zone Classification
    ai_res = ai_classify_geographic_zone(clean_addr)
    zone_label = ai_res["zone"]
    dist_name = ai_res["district"]

    # 0. 🧠 Persistent Location Memory Check (100% Score for returning customers)
    try:
        from database.db import get_saved_customer_location, save_customer_location
        saved_loc = get_saved_customer_location(raw_cust, clean_addr)
        if saved_loc:
            logger.info(f"🧠 Matched Database Location Memory (100%): '{raw_cust[:30]}' => ({saved_loc['lat']}, {saved_loc['lng']})")
            return {
                "lat": saved_loc["lat"],
                "lng": saved_loc["lng"],
                "raw_lat": saved_loc["lat"],
                "raw_lng": saved_loc["lng"],
                "verified_lat": saved_loc["lat"],
                "verified_lng": saved_loc["lng"],
                "formatted_address": saved_loc.get("formatted_address") or clean_addr,
                "zone": zone_label,
                "geocode_provider": "db_memory",
                "confidence_score": 100.0,
                "is_verified": True
            }
    except Exception as e:
        logger.warning(f"Database location memory check error: {e}")

    # 2. 🔍 Stage 1 Search: ค้นหาด้วย "ชื่อบริษัทเพียวๆ (ตัดโค้ดรหัสออกแล้ว) + ที่อยู่" (เพื่อความแม่นยำสูงสุด)
    online_place = None
    if clean_cust and len(clean_cust) > 2:
        combined_query = f"{clean_cust} {clean_addr}".strip()
        online_place = search_place_online(combined_query)

    # 3. 🔍 Stage 2 Search: หากไม่มีชื่อบริษัท หรือค้นหาด้วยชื่อบริษัทแล้วไม่เจอ ให้ค้นหาด้วย "ที่อยู่ดั้งเดิม"
    if not online_place:
        online_place = search_place_online(clean_addr)

    if online_place:
        lat, lng, display_name, provider, score = online_place
        
        # หากได้ความแม่นยำสูง (>=90%) ให้ Auto-save ลงความจำถาวร
        if score >= 90.0:
            try:
                from database.db import save_customer_location
                save_customer_location(raw_cust, clean_addr, lat, lng, display_name, score)
            except Exception as e:
                logger.warning(f"Error auto-saving high precision location: {e}")

        return {
            "lat": lat,
            "lng": lng,
            "raw_lat": lat,
            "raw_lng": lng,
            "verified_lat": lat,
            "verified_lng": lng,
            "formatted_address": display_name or clean_addr,
            "zone": zone_label,
            "geocode_provider": provider,
            "confidence_score": score,
            "is_verified": score >= 98.0
        }

    # 4. Stage 3 Search: หากยังไม่เจอที่อยู่เต็ม ให้ค้นหาเขต/อำเภอผ่าน Live API
    fallback_place = search_place_online(f"{dist_name} {ai_res.get('province', '')}")
    if fallback_place:
        lat, lng, display_name, provider, score = fallback_place
        return {
            "lat": lat,
            "lng": lng,
            "raw_lat": lat,
            "raw_lng": lng,
            "verified_lat": lat,
            "verified_lng": lng,
            "formatted_address": clean_addr,
            "zone": zone_label,
            "geocode_provider": f"{provider}_district",
            "confidence_score": 35.0,  # fallback ให้คะแนนต่ำเพื่อเตือนผู้ใช้
            "is_verified": False
        }

    # Default Depot Fallback
    return {
        "lat": depot_lat_val,
        "lng": depot_lng_val,
        "raw_lat": depot_lat_val,
        "raw_lng": depot_lng_val,
        "verified_lat": depot_lat_val,
        "verified_lng": depot_lng_val,
        "formatted_address": clean_addr,
        "zone": zone_label,
        "geocode_provider": "default",
        "confidence_score": 20.0,
        "is_verified": False
    }


def geocode_orders(orders: list[dict], force_refresh: bool = False) -> list[dict]:
    """Geocode และค้นหาสถานที่จริงสำหรับทุก orders ด้วย Google Maps / High Precision Search"""
    geocoded = []
    depot_lat_val = getattr(config, "DEPOT_LAT", 13.781882)
    for order in orders:
        has_coords = (order.get("lat") is not None and order.get("lng") is not None and 
                      order.get("lat") != depot_lat_val and order.get("zone"))
        
        if force_refresh or not has_coords:
            result = geocode_address(order.get("address", ""), customer=order.get("customer", ""))
            order["lat"] = result["lat"]
            order["lng"] = result["lng"]
            order["raw_lat"] = result.get("raw_lat", result["lat"])
            order["raw_lng"] = result.get("raw_lng", result["lng"])
            order["verified_lat"] = order.get("verified_lat", result["lat"])
            order["verified_lng"] = order.get("verified_lng", result["lng"])
            order["zone"] = result.get("zone", "ไม่ระบุ")
            order["geocode_provider"] = result.get("geocode_provider", "google")
            order["confidence_score"] = result.get("confidence_score", 30.0)
            order["is_verified"] = order.get("is_verified", False)

        geocoded.append(order)

    return geocoded
