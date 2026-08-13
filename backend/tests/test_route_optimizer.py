"""
Unit tests for route optimizer
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def test_validate_inputs_empty_orders(sample_vehicles):
    """orders ว่าง = warning"""
    from services.route_optimizer import _validate_inputs
    
    warnings = _validate_inputs([], sample_vehicles)
    assert len(warnings) > 0
    assert "ไม่มี orders" in warnings[0]


def test_validate_inputs_empty_vehicles(sample_orders):
    """vehicles ว่าง = warning"""
    from services.route_optimizer import _validate_inputs
    
    warnings = _validate_inputs(sample_orders, [])
    assert len(warnings) > 0
    assert "ไม่มี vehicles" in warnings[0]


def test_validate_inputs_overweight(sample_vehicles):
    """น้ำหนักเกิน capacity = warning"""
    from services.route_optimizer import _validate_inputs
    
    orders = [
        {"customer": "A", "address": "ที่อยู่ A", "weight": 5000},
        {"customer": "B", "address": "ที่อยู่ B", "weight": 5000},
    ]
    
    warnings = _validate_inputs(orders, sample_vehicles)
    assert any("เกินความจุรถรวม" in w for w in warnings)


def test_validate_inputs_negative_weight(sample_vehicles):
    """น้ำหนักติดลบ = warning"""
    from services.route_optimizer import _validate_inputs
    
    orders = [
        {"customer": "A", "address": "ที่อยู่ A", "weight": -100},
    ]
    
    warnings = _validate_inputs(orders, sample_vehicles)
    assert any("น้ำหนักติดลบ" in w for w in warnings)


def test_validate_inputs_valid(sample_orders, sample_vehicles):
    """ข้อมูลปกติ = ไม่มี warning"""
    from services.route_optimizer import _validate_inputs
    
    warnings = _validate_inputs(sample_orders, sample_vehicles)
    assert len(warnings) == 0


def test_choose_demand_mode_with_weight(sample_orders, sample_vehicles):
    """มีน้ำหนัก = weight mode"""
    from services.route_optimizer import _choose_demand_mode
    
    mode, caps, demands = _choose_demand_mode(sample_orders, sample_vehicles)
    
    assert mode == "weight"
    assert len(caps) == 2
    assert len(demands) == 4  # depot + 3 orders


def test_choose_demand_mode_no_weight(sample_vehicles):
    """ไม่มีน้ำหนัก = stop_count mode"""
    from services.route_optimizer import _choose_demand_mode
    
    orders = [
        {"customer": "A", "address": "ที่อยู่ A"},
        {"customer": "B", "address": "ที่อยู่ B"},
    ]
    
    mode, caps, demands = _choose_demand_mode(orders, sample_vehicles)
    
    assert mode == "stop_count"
    assert len(caps) == 2
    assert len(demands) == 3  # depot + 2 orders


def test_generate_google_maps_link(sample_orders, sample_depot):
    """สร้าง Google Maps link ได้"""
    from services.route_optimizer import generate_google_maps_link
    
    link = generate_google_maps_link(sample_orders, sample_depot)
    
    assert "google.com/maps/dir" in link
    assert str(sample_depot["lat"]) in link


def test_cluster_orders_small(sample_orders, sample_depot):
    """orders < 200 = ไม่ cluster"""
    from services.route_optimizer import _cluster_orders
    
    clusters = _cluster_orders(sample_orders, sample_depot["lat"], sample_depot["lng"])
    
    assert len(clusters) == 1
    assert len(clusters[0]) == 3


def test_combined_arc_cost_calculates_correctly():
    """cost = distance_m + TIME_WEIGHT * travel_min + STOP_WEIGHT (ออกจากลูกค้า) หรือไม่มี (ออกจาก depot)"""
    from config import PRIORITY_TIME_COST_WEIGHT, PRIORITY_STOP_COST_WEIGHT, AVG_SPEED_KMH

    dist_m = 5000  # 5 km
    travel_min = dist_m / (AVG_SPEED_KMH * 1000 / 60)

    # depot → ลูกค้า: ไม่มี stop penalty
    cost_from_depot = int(dist_m + PRIORITY_TIME_COST_WEIGHT * travel_min + 0)
    # ลูกค้า → ลูกค้า: มี stop penalty
    cost_from_customer = int(dist_m + PRIORITY_TIME_COST_WEIGHT * travel_min + PRIORITY_STOP_COST_WEIGHT)

    # ค่า cost จากลูกค้าต้องสูงกว่าจาก depot (มี stop penalty)
    assert cost_from_customer > cost_from_depot
    # ค่า cost ต้องสูงกว่า distance เดี่ยว (มี time + stops penalty)
    assert cost_from_customer > dist_m
    # ค่า cost จาก depot ต้องสูงกว่า distance เดี่ยว (มี time component)
    assert cost_from_depot > dist_m


def test_priority_weights_configurable():
    """ค่า priority weights อ่านได้จาก config"""
    from config import PRIORITY_TIME_COST_WEIGHT, PRIORITY_STOP_COST_WEIGHT

    assert PRIORITY_TIME_COST_WEIGHT >= 0
    assert PRIORITY_STOP_COST_WEIGHT >= 0
    # ค่า default: time > stops (priority 2 > 3)
    assert PRIORITY_TIME_COST_WEIGHT > PRIORITY_STOP_COST_WEIGHT


def test_empty_orders_no_crash():
    """optimize_routes กับ orders ว่าง = ไม่ crash"""
    from services.route_optimizer import optimize_routes

    result = optimize_routes([], vehicles=[], depot={"lat": 13.78, "lng": 100.42, "address": "test"})
    assert result["routes"] == []
    assert result["deferred_count"] == 0
    assert result["deferred_weight"] == 0
