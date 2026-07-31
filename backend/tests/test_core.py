import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from services.data_validator import validate_orders
from services.distance_matrix import _haversine, get_distance_matrix
from services.route_optimizer import optimize_routes


class TestDataValidator:
    def test_skip_empty_address(self):
        orders = [
            {"customer": "ลูกค้า A", "address": "", "weight": 10},
            {"customer": "ลูกค้า B", "address": "123 ถ.สุขุมวิท", "weight": 5},
        ]
        result = validate_orders(orders)
        assert len(result) == 1
        assert result[0]["customer"] == "ลูกค้า B"

    def test_default_customer_name(self):
        orders = [{"address": "123 ถ.สุขุมวิท", "weight": 5}]
        result = validate_orders(orders)
        assert result[0]["customer"] == "ลูกค้า #1"

    def test_default_weight(self):
        orders = [{"customer": "A", "address": "123 ถ.สุขุมวิท", "weight": 0}]
        result = validate_orders(orders)
        assert result[0]["weight"] == 1.0

    def test_negative_weight_becomes_default(self):
        orders = [{"customer": "A", "address": "123 ถ.สุขุมวิท", "weight": -5}]
        result = validate_orders(orders)
        assert result[0]["weight"] == 1.0

    def test_valid_order_passes(self):
        orders = [{"customer": "ลูกค้า A", "address": "123 ถ.สุขุมวิท", "weight": 10}]
        result = validate_orders(orders)
        assert len(result) == 1
        assert result[0]["weight"] == 10

    def test_clear_invalid_lat_lng(self):
        orders = [
            {"customer": "A", "address": "123", "weight": 1, "lat": 999, "lng": 999},
            {"customer": "B", "address": "456", "weight": 1, "lat": 13.7, "lng": 100.4},
        ]
        result = validate_orders(orders)
        assert result[0].get("lat") is None
        assert result[0].get("lng") is None
        assert result[1]["lat"] == 13.7

    def test_empty_list(self):
        result = validate_orders([])
        assert result == []


class TestHaversine:
    def test_same_point(self):
        assert _haversine(13.7, 100.4, 13.7, 100.4) == 0.0

    def test_known_distance(self):
        # Bangkok to Chiang Mai ~580km
        d = _haversine(13.7563, 100.5018, 18.7883, 98.9853)
        assert 550 < d < 620

    def test_symmetry(self):
        d1 = _haversine(13.7, 100.4, 14.0, 100.5)
        d2 = _haversine(14.0, 100.5, 13.7, 100.4)
        assert abs(d1 - d2) < 0.01


class TestDistanceMatrix:
    def test_depot_and_one_order(self):
        orders = [{"lat": 13.8, "lng": 100.5}]
        depot = {"lat": 13.7, "lng": 100.4}
        matrix = get_distance_matrix(orders, depot)
        assert len(matrix) == 2
        assert len(matrix[0]) == 2
        assert matrix[0][0] == 0.0
        assert matrix[1][1] == 0.0
        assert matrix[0][1] > 0

    def test_symmetric_matrix(self):
        orders = [{"lat": 13.8, "lng": 100.5}, {"lat": 13.6, "lng": 100.3}]
        depot = {"lat": 13.7, "lng": 100.4}
        matrix = get_distance_matrix(orders, depot)
        assert abs(matrix[0][1] - matrix[1][0]) < 0.01
        assert abs(matrix[0][2] - matrix[2][0]) < 0.01


class TestRouteOptimizer:
    def test_single_order_single_vehicle(self):
        orders = [
            {"id": 1, "customer": "A", "address": "123", "weight": 10, "lat": 13.8, "lng": 100.5}
        ]
        vehicles = [{"id": 1, "name": "V1", "plate": "กข 1", "capacity": 100, "driver": "A", "active": True}]
        routes = optimize_routes(orders, vehicles=vehicles)
        assert len(routes) == 1
        assert len(routes[0]["stops"]) == 1
        assert routes[0]["total_weight"] == 10

    def test_capacity_constraint(self):
        orders = [
            {"id": 1, "customer": "A", "address": "123", "weight": 60, "lat": 13.8, "lng": 100.5},
            {"id": 2, "customer": "B", "address": "456", "weight": 60, "lat": 13.9, "lng": 100.6},
        ]
        vehicles = [
            {"id": 1, "name": "V1", "plate": "กข 1", "capacity": 100, "driver": "A", "active": True},
            {"id": 2, "name": "V2", "plate": "กข 2", "capacity": 100, "driver": "B", "active": True},
        ]
        routes = optimize_routes(orders, vehicles=vehicles)
        total_stops = sum(len(r["stops"]) for r in routes)
        assert total_stops == 2

    def test_empty_orders(self):
        routes = optimize_routes([], vehicles=[])
        assert routes == []

    def test_output_has_required_fields(self):
        orders = [
            {"id": 1, "customer": "A", "address": "123", "weight": 10, "lat": 13.8, "lng": 100.5, "order_number": "SO001", "zone": "กรุงเทพ"},
        ]
        vehicles = [{"id": 1, "name": "V1", "plate": "กข 1", "capacity": 100, "driver": "A", "active": True}]
        routes = optimize_routes(orders, vehicles=vehicles)
        route = routes[0]
        assert "vehicle_id" in route
        assert "plate" in route
        assert "driver" in route
        assert "capacity" in route
        assert "stops" in route
        assert "total_weight" in route
        assert "google_maps_link" in route
        stop = route["stops"][0]
        assert stop["customer"] == "A"
        assert stop["order_number"] == "SO001"
        assert stop["zone"] == "กรุงเทพ"
