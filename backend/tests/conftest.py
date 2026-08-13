"""
Pytest configuration and fixtures
"""

import pytest
import os
import sys

# เพิ่ม path ของโปรเจกต์
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


@pytest.fixture
def sample_orders():
    """ตัวอย่าง orders สำหรับทดสอบ"""
    return [
        {
            "id": 1,
            "customer": "ลูกค้า A",
            "address": "123 ถนนสุขุมวิท แขวงคลองเตย เขตคลองเตย กรุงเทพมหานคร 10110",
            "weight": 100,
            "lat": 13.7310,
            "lng": 100.5670,
            "confidence_score": 95.0,
            "is_verified": True,
        },
        {
            "id": 2,
            "customer": "ลูกค้า B",
            "address": "456 ถนนรัชดาภิเษก แขวงดินแดง เขตดินแดง กรุงเทพมหานคร 10400",
            "weight": 200,
            "lat": 13.7650,
            "lng": 100.5700,
            "confidence_score": 85.0,
            "is_verified": False,
        },
        {
            "id": 3,
            "customer": "ลูกค้า C",
            "address": "789 ถนนลาดพร้าว แขวงวังทองหลาง เขตวังทองหลาง กรุงเทพมหานคร 10310",
            "weight": 150,
            "lat": 13.7700,
            "lng": 100.5800,
            "confidence_score": 70.0,
            "is_verified": False,
        },
    ]


@pytest.fixture
def sample_vehicles():
    """ตัวอย่าง vehicles สำหรับทดสอบ"""
    return [
        {"id": 1, "name": "รถคันที่ 1", "plate": "กข 1234", "capacity": 3750, "driver": "สมชาย", "active": True},
        {"id": 2, "name": "รถคันที่ 2", "plate": "กข 5678", "capacity": 1900, "driver": "สมศักดิ์", "active": True},
    ]


@pytest.fixture
def sample_depot():
    """ตัวอย่าง depot สำหรับทดสอบ"""
    return {
        "lat": 13.781882,
        "lng": 100.425041,
        "address": "บริษัท ทรีท็อปเคมิคัลแอนด์ฟู้ดส์ คอร์ปอเรชั่น จำกัด",
    }
