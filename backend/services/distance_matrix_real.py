"""
Enhanced Distance Matrix with Google Distance Matrix API
- Redis-backed caching via cache module
- Batch processing for >25 points
- Better error handling
- Config-based settings
"""

import logging
import time
from config import GOOGLE_MAPS_API_KEY, DEPOT_LAT, DEPOT_LNG
from services.geo_utils import haversine_km

logger = logging.getLogger(__name__)

# Lazy import googlemaps to avoid crash if not installed
_googlemaps = None

def _get_googlemaps():
    global _googlemaps
    if _googlemaps is None:
        try:
            import googlemaps
            _googlemaps = googlemaps
        except ImportError:
            logger.warning("googlemaps package not installed — using Haversine fallback")
    return _googlemaps

# Bounded in-memory cache with TTL (fallback when Redis unavailable)
import threading as _threading
_MATRIX_CACHE = {}
_MATRIX_CACHE_LOCK = _threading.Lock()
_CACHE_MAX_SIZE = 50
_CACHE_TTL_SECONDS = 3600  # 1 hour


def _cache_set(key, data):
    """Store in in-memory cache with eviction if over max size"""
    with _MATRIX_CACHE_LOCK:
        if len(_MATRIX_CACHE) >= _CACHE_MAX_SIZE:
            oldest_key = min(_MATRIX_CACHE, key=lambda k: _MATRIX_CACHE[k]["ts"])
            del _MATRIX_CACHE[oldest_key]
        _MATRIX_CACHE[key] = {"data": data, "ts": time.time()}


def _get_cached_matrix(key):
    """Try Redis cache first, then in-memory fallback."""
    from services.cache import get_cached, set_cached

    # 1. Try Redis
    redis_data = get_cached(f"dm:{key}")
    if redis_data is not None:
        return redis_data

    # 2. Try in-memory
    with _MATRIX_CACHE_LOCK:
        if key in _MATRIX_CACHE:
            entry = _MATRIX_CACHE[key]
            if time.time() - entry["ts"] < _CACHE_TTL_SECONDS:
                return entry["data"]
            del _MATRIX_CACHE[key]

    return None


def _set_cached_matrix(key, data):
    """Store in both Redis and in-memory cache."""
    from services.cache import set_cached

    # Store in Redis (TTL handled by cache module)
    set_cached(f"dm:{key}", data)

    # Also store in-memory for fast local access
    _cache_set(key, data)


def get_distance_matrix_real(orders: list[dict], depot: dict = None) -> list[list[float]]:
    """สร้าง distance matrix ระหว่างทุกจุด (depot + orders) พร้อม Redis + In-Memory Caching

    ใช้ Google Distance Matrix API สำหรับเส้นทางจริง
    Fallback เป็น Haversine ถ้า API error หรือ quota หมด
    """
    if depot is None:
        depot = {"lat": DEPOT_LAT, "lng": DEPOT_LNG}

    all_points = [depot] + orders

    # Cache key generated from points list
    cache_key = tuple((p.get("lat"), p.get("lng"), p.get("address")) for p in all_points)
    cached = _get_cached_matrix(cache_key)
    if cached is not None:
        logger.info("Distance Matrix cache hit")
        return cached

    if not GOOGLE_MAPS_API_KEY or GOOGLE_MAPS_API_KEY.startswith("YOUR_"):
        logger.info("ไม่มี GOOGLE_MAPS_API_KEY ที่ถูกต้อง — ใช้ Haversine distance matrix")
        res = _haversine_distance_matrix(all_points)
        _set_cached_matrix(cache_key, res)
        return res

    gmaps_module = _get_googlemaps()
    if not gmaps_module:
        logger.info("googlemaps not available — using Haversine distance matrix")
        res = _haversine_distance_matrix(all_points)
        _set_cached_matrix(cache_key, res)
        return res

    try:
        gmaps = gmaps_module.Client(key=GOOGLE_MAPS_API_KEY)

        origins = []
        for point in all_points:
            if point.get("lat") and point.get("lng"):
                origins.append(f"{point['lat']},{point['lng']}")
            else:
                origins.append(point.get("address", "กรุงเทพฯ"))

        if len(origins) > 25:
            logger.info(f"จำนวนจุด ({len(origins)}) เกิน 25 — แบ่ง batch เรียก Google API")
            matrix = _batch_distance_matrix(gmaps, origins)
        else:
            matrix = _single_distance_matrix(gmaps, origins)

        if matrix:
            logger.info(f"Distance matrix สร้างเสร็จ: {len(matrix)}x{len(matrix[0])}")
            _set_cached_matrix(cache_key, matrix)
            return matrix
        else:
            logger.warning("Google Distance Matrix API ไม่สำเร็จ — ใช้ Haversine fallback")
            res = _haversine_distance_matrix(all_points)
            _set_cached_matrix(cache_key, res)
            return res

    except Exception as e:
        logger.warning(f"Distance matrix API error: {e} — ใช้ Haversine distance matrix สำรอง")
        res = _haversine_distance_matrix(all_points)
        _set_cached_matrix(cache_key, res)
        return res


def _single_distance_matrix(gmaps, origins: list[str]) -> list[list[float]] | None:
    """เรียก Google Distance Matrix API สำหรับจุด <= 25 จุด"""
    try:
        result = gmaps.distance_matrix(origins, origins, mode="driving", language="th")

        matrix = []
        for row in result["rows"]:
            row_distances = []
            for element in row["elements"]:
                if element["status"] == "OK":
                    row_distances.append(element["distance"]["value"] / 1000)
                else:
                    row_distances.append(float("inf"))
            matrix.append(row_distances)

        return matrix
    except Exception as e:
        logger.error(f"Single distance matrix error: {e}")
        return None


def _batch_distance_matrix(gmaps, origins: list[str], batch_size: int = 25) -> list[list[float]] | None:
    """แบ่ง batch เรียก Google Distance Matrix API สำหรับจุด > 25 จุด (จำกัดไม่เกิน 625 elements/req)"""
    try:
        n = len(origins)
        matrix = [[0.0] * n for _ in range(n)]

        safe_batch = min(batch_size, max(1, 625 // n))
        if safe_batch < batch_size:
            logger.info(f"Reducing batch size from {batch_size} to {safe_batch} to stay under Google element limit")

        for i in range(0, n, safe_batch):
            batch_origins = origins[i:i + safe_batch]

            result = gmaps.distance_matrix(batch_origins, origins, mode="driving", language="th")

            for row_idx, row in enumerate(result["rows"]):
                for col_idx, element in enumerate(row["elements"]):
                    if element["status"] == "OK":
                        matrix[i + row_idx][col_idx] = element["distance"]["value"] / 1000
                    else:
                        matrix[i + row_idx][col_idx] = float("inf")

        return matrix
    except Exception as e:
        logger.error(f"Batch distance matrix error: {e}")
        return None


def _haversine_distance_matrix(points: list[dict]) -> list[list[float]]:
    """Mock distance matrix โดยใช้ระยะทาง Haversine จาก lat/lng"""
    n = len(points)
    matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i != j:
                lat1 = points[i].get("lat", DEPOT_LAT)
                lng1 = points[i].get("lng", DEPOT_LNG)
                lat2 = points[j].get("lat", DEPOT_LAT)
                lng2 = points[j].get("lng", DEPOT_LNG)
                matrix[i][j] = round(haversine_km(lat1, lng1, lat2, lng2), 2)

    return matrix


def clear_cache():
    """ล้าง cache ของ distance matrix"""
    from services.cache import delete_cached
    _MATRIX_CACHE.clear()
    logger.info("Distance matrix cache cleared")
