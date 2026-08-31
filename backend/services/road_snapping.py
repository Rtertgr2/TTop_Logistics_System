"""Google Roads API integration with bounded batching and safe fallbacks."""

import logging
import math
from collections.abc import Iterable

import requests

from config import (
    SNAP_TO_ROAD_ENABLED,
    SNAP_TO_ROAD_MAX_DISTANCE_M,
    SNAP_TO_ROAD_MAX_POINTS,
    SNAP_TO_ROAD_TIMEOUT_SECONDS,
)
from services.cache import get_cached, set_cached
from services.geo_utils import haversine_km
from services.geocoding import get_google_maps_api_key, is_in_thailand

logger = logging.getLogger(__name__)

ROADS_NEAREST_URL = "https://roads.googleapis.com/v1/nearestRoads"
GOOGLE_MAX_POINTS = 100


def _normalise_point(point) -> tuple[float, float] | None:
    if isinstance(point, dict):
        lat, lng = point.get("lat"), point.get("lng")
    elif isinstance(point, (tuple, list)) and len(point) >= 2:
        lat, lng = point[0], point[1]
    else:
        return None

    try:
        lat, lng = float(lat), float(lng)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(lat) or not math.isfinite(lng) or not is_in_thailand(lat, lng):
        return None
    return lat, lng


def _fallback(lat: float | None, lng: float | None, reason: str) -> dict:
    return {
        "input_lat": lat,
        "input_lng": lng,
        "lat": lat,
        "lng": lng,
        "distance_m": 0.0 if lat is not None and lng is not None else None,
        "place_id": None,
        "provider": "original",
        "snapped": False,
        "reason": reason,
    }


def _cache_key(lat: float, lng: float) -> str:
    return f"road:{lat:.6f}:{lng:.6f}"


def _snap_chunk(chunk: list[tuple[int, float, float]], api_key: str) -> dict[int, dict]:
    points = "|".join(f"{lat:.7f},{lng:.7f}" for _, lat, lng in chunk)
    try:
        response = requests.get(
            ROADS_NEAREST_URL,
            params={"points": points, "key": api_key},
            timeout=SNAP_TO_ROAD_TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            logger.warning("Google Roads API returned HTTP %s", response.status_code)
            return {}
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Google Roads API request failed: %s", exc)
        return {}

    snapped = {}
    for item in payload.get("snappedPoints", []):
        relative_index = item.get("originalIndex")
        location = item.get("location", {})
        if not isinstance(relative_index, int):
            continue
        if not isinstance(location, dict):
            continue
        try:
            snapped[relative_index] = {
                "lat": float(location["latitude"]),
                "lng": float(location["longitude"]),
                "place_id": item.get("placeId"),
            }
        except (KeyError, TypeError, ValueError):
            continue
    return snapped


def snap_nearest_roads(points: Iterable, enabled: bool | None = None) -> list[dict]:
    """Snap independent coordinates to nearby roads using Google Nearest Roads."""
    points = list(points)
    normalised = [_normalise_point(point) for point in points]
    use_api = SNAP_TO_ROAD_ENABLED if enabled is None else enabled

    if not use_api:
        return [
            _fallback(pair[0], pair[1], "disabled")
            if pair
            else _fallback(None, None, "invalid_coordinate")
            for pair in normalised
        ]

    api_key = get_google_maps_api_key()
    if not api_key or api_key.startswith("YOUR_"):
        return [
            _fallback(pair[0], pair[1], "missing_api_key")
            if pair
            else _fallback(None, None, "invalid_coordinate")
            for pair in normalised
        ]

    max_points = min(max(int(SNAP_TO_ROAD_MAX_POINTS), 1), GOOGLE_MAX_POINTS)
    results = [
        _fallback(pair[0], pair[1], "invalid_coordinate")
        if pair
        else _fallback(None, None, "invalid_coordinate")
        for pair in normalised
    ]
    pending: list[tuple[int, float, float]] = []

    for index, pair in enumerate(normalised):
        if pair is None:
            continue
        lat, lng = pair
        cached = get_cached(_cache_key(lat, lng))
        if cached is not None:
            results[index] = cached
        else:
            pending.append((index, lat, lng))

    for start in range(0, len(pending), max_points):
        chunk = pending[start : start + max_points]
        snapped = _snap_chunk(chunk, api_key)
        for relative_index, (index, input_lat, input_lng) in enumerate(chunk):
            road_point = snapped.get(relative_index)
            if not road_point:
                result = _fallback(input_lat, input_lng, "api_no_match")
            else:
                snapped_lat, snapped_lng = road_point["lat"], road_point["lng"]
                distance_m = round(
                    haversine_km(input_lat, input_lng, snapped_lat, snapped_lng) * 1000,
                    1,
                )
                if not is_in_thailand(snapped_lat, snapped_lng):
                    result = _fallback(input_lat, input_lng, "snap_outside_thailand")
                elif distance_m > SNAP_TO_ROAD_MAX_DISTANCE_M:
                    result = _fallback(input_lat, input_lng, "snap_too_far")
                else:
                    result = {
                        "input_lat": input_lat,
                        "input_lng": input_lng,
                        "lat": snapped_lat,
                        "lng": snapped_lng,
                        "distance_m": distance_m,
                        "place_id": road_point.get("place_id"),
                        "provider": "google_nearest_roads",
                        "snapped": True,
                        "reason": None,
                    }
            results[index] = result
            set_cached(_cache_key(input_lat, input_lng), result)

    return results


def snap_to_road(lat: float, lng: float, enabled: bool | None = None) -> dict:
    """Convenience wrapper for a single coordinate."""
    return snap_nearest_roads([{"lat": lat, "lng": lng}], enabled=enabled)[0]
