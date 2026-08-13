"""
Unit tests for Haversine distance calculation
"""

import pytest
import math
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_haversine_same_point():
    """ระยะทางระหว่างจุดเดียวกัน = 0"""
    from services.geo_utils import haversine_km
    
    result = haversine_km(13.7310, 100.5670, 13.7310, 100.5670)
    assert result == 0.0


def test_haversine_known_distance():
    """ทดสอบระยะทางที่รู้ค่า (กรุงเทพฯ → พัทยา ≈ 101 km)"""
    from services.geo_utils import haversine_km
    
    # Bangkok: 13.7563, 100.5018
    # Pattaya: 12.9236, 100.8825
    result = haversine_km(13.7563, 100.5018, 12.9236, 100.8825)
    
    # ระยะทาง Haversine จริง ≈ 101 km (±10 km)
    assert 90 <= result <= 110


def test_haversine_symmetry():
    """ระยะทาง A→B = B→A"""
    from services.geo_utils import haversine_km
    
    dist_ab = haversine_km(13.7310, 100.5670, 13.7650, 100.5700)
    dist_ba = haversine_km(13.7650, 100.5700, 13.7310, 100.5670)
    
    assert abs(dist_ab - dist_ba) < 0.001


def test_haversine_triangle_inequality():
    """ทดสอบ triangle inequality: A→B + B→C >= A→C"""
    from services.geo_utils import haversine_km
    
    dist_ab = haversine_km(13.7310, 100.5670, 13.7650, 100.5700)
    dist_bc = haversine_km(13.7650, 100.5700, 13.7700, 100.5800)
    dist_ac = haversine_km(13.7310, 100.5670, 13.7700, 100.5800)
    
    assert dist_ab + dist_bc >= dist_ac - 0.001


def test_haversine_positive():
    """ระยะทางต้องเป็นบวกเสมอ"""
    from services.geo_utils import haversine_km
    
    result = haversine_km(13.7310, 100.5670, 13.7650, 100.5700)
    assert result > 0
