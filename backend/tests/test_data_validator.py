"""
Unit tests for data validator
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_validate_orders_empty():
    """orders ว่าง = คืน list ว่าง"""
    from services.data_validator import validate_orders
    
    result = validate_orders([])
    assert result == []


def test_validate_orders_valid():
    """orders ที่มีข้อมูลครบ = ผ่าน validation"""
    from services.data_validator import validate_orders
    
    orders = [
        {
            "customer": "ลูกค้า A",
            "address": "123 ถนนสุขุมวิท",
            "weight": 100,
        }
    ]
    
    result = validate_orders(orders)
    assert len(result) == 1
    assert result[0]["customer"] == "ลูกค้า A"


def test_validate_orders_missing_customer():
    """orders ที่ไม่มี customer = ตั้งค่า default"""
    from services.data_validator import validate_orders
    
    orders = [
        {
            "address": "123 ถนนสุขุมวิท",
            "weight": 100,
        }
    ]
    
    result = validate_orders(orders)
    assert len(result) == 1
    assert result[0]["customer"] == "ลูกค้า #1"


def test_validate_orders_missing_weight():
    """orders ที่ไม่มี weight = ตั้งค่า default 1.0"""
    from services.data_validator import validate_orders
    
    orders = [
        {
            "customer": "ลูกค้า A",
            "address": "123 ถนนสุขุมวิท",
        }
    ]
    
    result = validate_orders(orders)
    assert len(result) == 1
    assert result[0]["weight"] == 1.0


def test_validate_orders_multiple():
    """orders หลายรายการ = ผ่าน validation ทั้งหมด"""
    from services.data_validator import validate_orders
    
    orders = [
        {"customer": "ลูกค้า A", "address": "ที่อยู่ A", "weight": 100},
        {"customer": "ลูกค้า B", "address": "ที่อยู่ B", "weight": 200},
        {"customer": "ลูกค้า C", "address": "ที่อยู่ C", "weight": 150},
    ]
    
    result = validate_orders(orders)
    assert len(result) == 3
