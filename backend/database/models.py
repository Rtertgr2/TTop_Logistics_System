from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, DateTime, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

Base = declarative_base()


def _utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    role = Column(String(50), default="user")  # admin, dispatcher, driver, user
    name = Column(String(200), default="")
    email = Column(String(200), default="")
    phone = Column(String(50), default="")
    department = Column(String(100), default="")
    position = Column(String(100), default="")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    def to_dict(self) -> dict:
        """Return a consistent dictionary representation of the user."""
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "name": self.name or self.username,
            "email": self.email or "",
            "phone": self.phone or "",
            "department": self.department or "",
            "position": self.position or "",
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)  # create, update, deactivate, activate, change_password, login_failed
    target_user = Column(String(100), default="")
    details = Column(Text, default="")
    timestamp = Column(DateTime, default=_utcnow)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index('ix_orders_created_at', 'created_at'),
        Index('ix_orders_customer', 'customer'),
        Index('ix_orders_order_number', 'order_number'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_number = Column(String(100))
    customer = Column(String(500), nullable=False)
    address = Column(Text, nullable=False)
    weight = Column(Float, default=0)
    source_file = Column(String(500))
    lat = Column(Float)
    lng = Column(Float)
    raw_lat = Column(Float)
    raw_lng = Column(Float)
    verified_lat = Column(Float)
    verified_lng = Column(Float)
    confidence_score = Column(Float, default=0)
    geocode_provider = Column(String(100), default='none')
    is_verified = Column(Boolean, default=False)
    verified_by = Column(String(100))
    verified_at = Column(DateTime)
    zone = Column(String(100))
    products_json = Column(Text)
    # Time Window fields (Sprint 2.1)
    time_window_start = Column(String(10))  # "08:00"
    time_window_end = Column(String(10))    # "17:00"
    time_window_source = Column(String(20), default='none')  # "pdf", "manual", "none"
    delivery_date = Column(String(10))  # "2026-08-15"
    booking_status = Column(String(50), default='pending')  # pending, booked, delivered
    created_at = Column(DateTime, default=_utcnow)

    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_code = Column(String(100))
    product_name = Column(String(500))
    quantity = Column(Float, default=0)
    unit = Column(String(50), default='ชิ้น')
    price = Column(Float, default=0)
    total = Column(Float, default=0)
    item_weight = Column(Float, default=0)  # น้ำหนักรวม = จำนวน × น้ำหนักต่อหน่วย

    order = relationship("Order", back_populates="items")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200))
    plate = Column(String(100), nullable=False)
    driver = Column(String(200))
    capacity = Column(Float, default=5000)
    max_volume_cbm = Column(Float, default=0)
    max_boxes = Column(Integer, default=0)
    max_stops = Column(Integer, default=0)
    line_user_id = Column(String(200), default="")
    active = Column(Boolean, default=True)


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_code = Column(String(100), unique=True, nullable=False, index=True)
    product_name = Column(String(500), nullable=False)
    weight = Column(Float, default=0)
    created_at = Column(DateTime, default=_utcnow)


class RoutePlan(Base):
    __tablename__ = "route_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_date = Column(DateTime, nullable=False)
    total_orders = Column(Integer, default=0)
    total_vehicles = Column(Integer, default=0)
    depot_address = Column(Text)
    created_at = Column(DateTime, default=_utcnow)

    details = relationship("RouteDetail", back_populates="plan", cascade="all, delete-orphan")


class RouteDetail(Base):
    __tablename__ = "route_details"
    __table_args__ = (
        Index('ix_route_details_plan_id', 'plan_id'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, ForeignKey("route_plans.id", ondelete="CASCADE"), nullable=False)
    vehicle_id = Column(Integer, nullable=False)
    plate = Column(String(100))
    driver = Column(String(200))
    total_weight = Column(Float)
    google_maps_link = Column(Text)
    stops_json = Column(Text)

    plan = relationship("RoutePlan", back_populates="details")


class CustomerLocation(Base):
    __tablename__ = "customer_locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_key = Column(String(500), unique=True, nullable=False)
    address_key = Column(String(500))
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    formatted_address = Column(Text)
    confidence_score = Column(Float, default=100.0)
    updated_at = Column(DateTime, default=_utcnow)


class Driver(Base):
    __tablename__ = "drivers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    phone = Column(String(50))
    line_user_id = Column(String(200))
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="SET NULL"))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_utcnow)

    vehicle = relationship("Vehicle", backref="drivers")


class VehicleLoad(Base):
    __tablename__ = "vehicle_loads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False, unique=True)
    current_weight = Column(Float, default=0)
    current_volume = Column(Float, default=0)
    current_boxes = Column(Integer, default=0)
    current_stops = Column(Integer, default=0)
    updated_at = Column(DateTime, default=_utcnow)

    vehicle = relationship("Vehicle", backref="load")


class StopStatusHistory(Base):
    __tablename__ = "stop_status_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stop_id = Column(Integer, nullable=False)
    route_id = Column(Integer, ForeignKey("route_details.id", ondelete="CASCADE"))
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"))
    status = Column(String(50), nullable=False)  # PENDING, IN_TRANSIT, ARRIVED, DELIVERED, FAILED, PARTIAL, RESCHEDULED
    timestamp = Column(DateTime, default=_utcnow)
    updated_by = Column(String(100))
    note = Column(Text)


class ItemDelivery(Base):
    __tablename__ = "item_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stop_id = Column(Integer, nullable=False)
    order_item_id = Column(Integer, ForeignKey("order_items.id", ondelete="CASCADE"))
    ordered_qty = Column(Float, default=0)
    delivered_qty = Column(Float, default=0)
    status = Column(String(50), default='pending')  # pending, delivered, partial, failed
    note = Column(Text)
    created_at = Column(DateTime, default=_utcnow)


class RouteTransfer(Base):
    __tablename__ = "route_transfers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stop_id = Column(Integer, nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"))
    from_route_id = Column(Integer, ForeignKey("route_details.id", ondelete="SET NULL"))
    to_route_id = Column(Integer, ForeignKey("route_details.id", ondelete="SET NULL"))
    from_vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="SET NULL"))
    to_vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="SET NULL"))
    transfer_type = Column(String(50))  # overflow, underflow, manual
    reason = Column(Text)
    approved_by = Column(String(100))
    created_at = Column(DateTime, default=_utcnow)


class VehicleLocation(Base):
    __tablename__ = "vehicle_locations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id", ondelete="CASCADE"), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    speed_kmh = Column(Float, default=0)
    heading = Column(Float, default=0)
    recorded_at = Column(DateTime, default=_utcnow)
