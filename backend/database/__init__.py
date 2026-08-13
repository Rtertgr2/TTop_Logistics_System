"""Database package — re-exports for backward compatibility."""

from database.connection import (
    engine,
    SessionLocal,
    get_db,
    check_db_connection,
    get_db_status,
    init_db,
    _business_today,
    _record_db_metric,
)

from database.order_db import (
    save_orders,
    get_all_orders,
    get_today_orders,
    update_order_location,
)

from database.vehicle_db import (
    save_vehicles_to_db,
    get_vehicles_from_db,
    delete_vehicle_from_db,
)

from database.route_db import (
    save_route_plan,
    get_today_active_routes,
    get_route_history,
    get_route_driver_name,
    get_driver_route,
    clear_all_data,
)

from database.delivery_db import (
    update_stop_status,
    get_stop_status_history,
    get_delivery_dashboard,
    update_item_delivery,
    reschedule_stop,
)

from database.location_db import (
    get_saved_customer_location,
    save_customer_location,
    get_all_customer_locations,
    delete_customer_location,
)

__all__ = [
    "engine", "SessionLocal", "get_db", "check_db_connection", "get_db_status", "init_db",
    "_business_today", "_record_db_metric",
    "save_orders", "get_all_orders", "get_today_orders", "update_order_location",
    "save_vehicles_to_db", "get_vehicles_from_db", "delete_vehicle_from_db",
    "save_route_plan", "get_today_active_routes", "get_route_history",
    "get_route_driver_name", "get_driver_route", "clear_all_data",
    "update_stop_status", "get_stop_status_history", "get_delivery_dashboard",
    "update_item_delivery", "reschedule_stop",
    "get_saved_customer_location", "save_customer_location",
    "get_all_customer_locations", "delete_customer_location",
]
