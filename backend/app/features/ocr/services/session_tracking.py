from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import ParkingSession


def record_entry(db: Session, vehicle_id: int, zone_id: int, entry_time: datetime) -> None:
    """
    Opens a new IN session for this vehicle, unless one is already open —
    guards a retriggered Entry event from inflating the valid-session count.
    """
    already_in = (
        db.query(ParkingSession)
        .filter(ParkingSession.vehicle_id == vehicle_id, ParkingSession.status == "IN")
        .first()
    )
    if already_in is not None:
        return

    db.add(ParkingSession(
        vehicle_id=vehicle_id,
        zone_id=zone_id,
        entry_time=entry_time,
        status="IN",
    ))


def record_exit(db: Session, vehicle_id: int, exit_time: datetime) -> None:
    """
    Closes the most recent open session for this vehicle, if any.
    """
    active_session = (
        db.query(ParkingSession)
        .filter(ParkingSession.vehicle_id == vehicle_id, ParkingSession.status == "IN")
        .order_by(ParkingSession.entry_time.desc())
        .first()
    )
    if active_session is not None:
        active_session.status = "OUT"
        active_session.exit_time = exit_time
