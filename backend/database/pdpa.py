"""PDPA / GDPR compliance helpers.

NOTE: reconstructed (original source was unreadable / corrupted on disk).
`api/routes.py` imports: export_user_personal_data, delete_user_personal_data,
purge_expired_customer_data.
"""

from datetime import datetime, timezone, timedelta

from database.db import SessionLocal
from database.models import (
    Order,
    OrderItem,
    CustomerLocation,
    StopStatusHistory,
    ItemDelivery,
)


def export_user_personal_data(user_id: int) -> dict | None:
    """Data Subject Access Request: collect personal data tied to a user."""
    db = SessionLocal()
    try:
        # Import here to avoid circular import at module load
        from database.models import User as UserModel

        row = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not row:
            return None
        return {
            "user": row.to_dict(),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "note": "Export includes profile + consent records for this account.",
        }
    finally:
        db.close()


def delete_user_personal_data(user_id: int) -> bool:
    """Right to erasure: anonymise/delete the user's personal record."""
    db = SessionLocal()
    try:
        from database.models import User as UserModel

        row = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not row:
            return False
        # Anonymise personal fields (keep row for referential integrity)
        row.name = ""
        row.email = ""
        row.phone = ""
        row.department = ""
        row.position = ""
        row.consent_given = False
        db.commit()
        return True
    finally:
        db.close()


def purge_expired_customer_data(retention_days: int) -> dict:
    """Delete customer orders/locations older than retention_days (PDPA retention)."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        old_orders = (
            db.query(Order).filter(Order.created_at < cutoff).all()
        )
        deleted_orders = len(old_orders)
        for o in old_orders:
            db.query(OrderItem).filter(OrderItem.order_id == o.id).delete()
            db.query(StopStatusHistory).filter(StopStatusHistory.order_id == o.id).delete()
            db.query(ItemDelivery).filter(ItemDelivery.stop_id.in_(
                [s.id for s in db.query(StopStatusHistory).filter(StopStatusHistory.order_id == o.id)]
            )).delete(synchronize_session=False)
        db.query(Order).filter(Order.created_at < cutoff).delete()
        deleted_locations = (
            db.query(CustomerLocation)
            .filter(CustomerLocation.updated_at < cutoff)
            .delete()
        )
        db.commit()
        return {
            "deleted_orders": deleted_orders,
            "deleted_customer_locations": deleted_locations,
            "cutoff": cutoff.isoformat(),
        }
    finally:
        db.close()
