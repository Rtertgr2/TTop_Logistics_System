"""Shared geographic helper functions."""
import math

_EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two points in kilometres.

    Uses the haversine formula with a clamp on ``a`` to keep it inside the
    valid domain for ``asin`` (floating-point rounding can push it slightly
    out of ``[0, 1]``).
    """
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    a = max(0.0, min(1.0, a))
    return _EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(a))
