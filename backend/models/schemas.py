from pydantic import BaseModel
from typing import Optional


class Product(BaseModel):
    code: str
    name: str
    quantity: float
    unit: str = "ชิ้น"
    price: float = 0
    total: float = 0


class Order(BaseModel):
    customer: str
    address: str
    weight: float
    source_file: Optional[str] = None
    products: Optional[list[Product]] = None
    order_number: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    zone: Optional[str] = None


class PlanRoutesRequest(BaseModel):
    orders: list[Order]
    depot_address: Optional[str] = None


class RouteStop(BaseModel):
    customer: str
    address: str
    weight: float
    lat: Optional[float] = None
    lng: Optional[float] = None
    order_number: Optional[str] = None
    zone: Optional[str] = None


class VehicleRoute(BaseModel):
    vehicle_id: int
    name: str = ""
    plate: str = ""
    driver: str = ""
    capacity: float = 0
    stops: list[RouteStop]
    total_weight: float
    google_maps_link: str = ""


class RoutePlanResponse(BaseModel):
    routes: list[VehicleRoute]
    total_orders: int = 0
    total_vehicles: int = 0


class SendEmailRequest(BaseModel):
    routes: list[VehicleRoute]
    recipient: str
