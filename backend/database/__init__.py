"""Database package — re-exports for backward compatibility."""

from database.connection import (
    SessionLocal,
    _business_today,
    _record_db_metric,
    check_db_connection,
    engine,
    get_db,
    get_db_status,
    init_db,
)
from database.delivery_db import (
    get_delivery_dashboard,
    get_stop_status_history,
    reschedule_stop,
    update_item_delivery,
    update_stop_status,
)
from database.location_db import (
    delete_customer_location,
    get_all_customer_locations,
    get_saved_customer_location,
    save_customer_location,
)
from database.order_db import (
    get_all_orders,
    get_today_orders,
    save_orders,
    update_order_location,
)
from database.route_db import (
    clear_all_data,
    get_driver_route,
    get_route_driver_name,
    get_route_history,
    get_today_active_routes,
    save_route_plan,
)
from database.vehicle_db import (
    delete_vehicle_from_db,
    get_vehicles_from_db,
    save_vehicles_to_db,
)

__all__ = [
    "SessionLocal",
    "_business_today",
    "_record_db_metric",
    "check_db_connection",
    "clear_all_data",
    "delete_customer_location",
    "delete_vehicle_from_db",
    "engine",
    "get_all_customer_locations",
    "get_all_orders",
    "get_db",
    "get_db_status",
    "get_delivery_dashboard",
    "get_driver_route",
    "get_route_driver_name",
    "get_route_history",
    "get_saved_customer_location",
    "get_stop_status_history",
    "get_today_active_routes",
    "get_today_orders",
    "get_vehicles_from_db",
    "init_db",
    "reschedule_stop",
    "save_customer_location",
    "save_orders",
    "save_route_plan",
    "save_vehicles_to_db",
    "update_item_delivery",
    "update_order_location",
    "update_stop_status",
]
