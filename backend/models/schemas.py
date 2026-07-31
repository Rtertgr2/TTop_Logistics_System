from pydantic import BaseModel
from typing import Optional


class Product(BaseModel):
    code: str = ""
    name: str = ""
    quantity: float = 0
    unit: str = "ชิ้น"
    price: float = 0
    total: float = 0


class Order(BaseModel):
    customer: str
    address: str
    weight: float = 0
    source_file: Optional[str] = None
    products: Optional[list[Product]] = None
    order_number: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    zone: Optional[str] = None
    raw_lat: Optional[float] = None
    raw_lng: Optional[float] = None
    verified_lat: Optional[float] = None
    verified_lng: Optional[float] = None
    confidence_score: Optional[float] = None
    geocode_provider: Optional[str] = None
    is_verified: Optional[bool] = False


class RouteStop(BaseModel):
    id: Optional[int] = None
    customer: str = ""
    address: str = ""
    weight: float = 0
    lat: Optional[float] = None
    lng: Optional[float] = None
    order_number: Optional[str] = None
    zone: Optional[str] = None
    products: Optional[list[Product]] = None


class VehicleRoute(BaseModel):
    vehicle_id: int
    name: str = ""
    plate: str = ""
    driver: str = ""
    capacity: float = 0
    stops: list[RouteStop]
    total_weight: float = 0
    total_distance_km: float = 0
    google_maps_link: str = ""


class RoutePlanResponse(BaseModel):
    routes: list[VehicleRoute]
    total_orders: int = 0
    total_vehicles: int = 0


class PlanRoutesRequest(BaseModel):
    orders: list[Order]
    depot_address: Optional[str] = None
    depot_lat: Optional[float] = None
    depot_lng: Optional[float] = None


class SendEmailRequest(BaseModel):
    routes: list[VehicleRoute]
    recipient: str


class VerifyLocationRequest(BaseModel):
    lat: float
    lng: float
    verified_by: Optional[str] = "user"
