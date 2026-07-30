import logging
import googlemaps
from config import GOOGLE_MAPS_API_KEY, DEPOT_LAT, DEPOT_LNG

logger = logging.getLogger(__name__)

# High-performance in-memory cache for distance matrices
_MATRIX_CACHE = {}


def get_distance_matrix(orders: list[dict], depot: dict = None) -> list[list[float]]:
    """สร้าง distance matrix ระหว่างทุกจุด (depot + orders) พร้อม In-Memory Caching"""
    if depot is None:
        depot = {"lat": DEPOT_LAT, "lng": DEPOT_LNG}

    all_points = [depot] + orders

    # Cache key generated from points list
    cache_key = tuple((p.get("lat"), p.get("lng"), p.get("address")) for p in all_points)
    if cache_key in _MATRIX_CACHE:
        logger.info(f"⚡ คืนค่า Distance Matrix จาก In-Memory Cache (ความเร็ว 0ms)")
        return _MATRIX_CACHE[cache_key]

    if not GOOGLE_MAPS_API_KEY or GOOGLE_MAPS_API_KEY.startswith("YOUR_"):
        logger.info("ไม่มี GOOGLE_MAPS_API_KEY ที่ถูกต้อง — ใช้ Haversine distance matrix")
        res = _mock_distance_matrix(all_points)
        _MATRIX_CACHE[cache_key] = res
        return res

    try:
        gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

        origins = []
        for point in all_points:
            if point.get("lat") and point.get("lng"):
                origins.append(f"{point['lat']},{point['lng']}")
            else:
                origins.append(point.get("address", "กรุงเทพฯ"))

        destinations = origins.copy()

        if len(origins) > 25:
            logger.warning(f"จำนวนจุด ({len(origins)}) เกิน 25 — ใช้ Haversine distance matrix")
            return _mock_distance_matrix(all_points)

        result = gmaps.distance_matrix(origins, destinations, mode="driving", language="th")

        matrix = []
        for row in result["rows"]:
            row_distances = []
            for element in row["elements"]:
                if element["status"] == "OK":
                    row_distances.append(element["distance"]["value"] / 1000)
                else:
                    row_distances.append(float("inf"))
            matrix.append(row_distances)

        logger.info(f"Distance matrix สร้างเสร็จ: {len(matrix)}x{len(matrix[0])}")
        _MATRIX_CACHE[cache_key] = matrix
        return matrix

    except Exception as e:
        logger.warning(f"Distance matrix API error: {e} — ใช้ Haversine distance matrix สำรอง")
        res = _mock_distance_matrix(all_points)
        _MATRIX_CACHE[cache_key] = res
        return res


def _mock_distance_matrix(points: list[dict]) -> list[list[float]]:
    """Mock distance matrix โดยใช้ระยะทาง Haversine จาก lat/lng"""
    n = len(points)
    matrix = [[0.0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i != j:
                lat1 = points[i].get("lat", 13.7815)
                lng1 = points[i].get("lng", 100.4260)
                lat2 = points[j].get("lat", 13.7815)
                lng2 = points[j].get("lng", 100.4260)
                matrix[i][j] = _haversine(lat1, lng1, lat2, lng2)

    return matrix


def _haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """คำนวณระยะทาง Haversine (km) ระหว่าง 2 จุด"""
    import math

    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return round(R * c, 2)
