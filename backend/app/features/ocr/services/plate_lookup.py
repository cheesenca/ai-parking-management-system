from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import Vehicle
from app.features.ocr.pipeline.plate_utils import format_plate_display


def find_vehicle_by_plate(db: Session, plate_compact: str) -> Vehicle | None:
    """
    Looks up a Vehicle by a space-stripped, uppercased plate (see
    plate_utils.normalize_plate) against the space-containing stored format.
    """
    if not plate_compact:
        return None
    return (
        db.query(Vehicle)
        .filter(func.upper(func.replace(Vehicle.plate_number, ' ', '')) == plate_compact)
        .first()
    )


def resolve_or_create_vehicle(db: Session, plate_compact: str, vehicle_type: str = "Car") -> Vehicle:
    """
    Finds the registered Vehicle for a plate, or auto-registers it as an
    unregistered Visitor vehicle if it doesn't exist yet. Callers are
    responsible for having already confirmed the plate is admissible
    (registered, or format-valid) before calling this.
    """
    vehicle = find_vehicle_by_plate(db, plate_compact)
    if vehicle is not None:
        return vehicle

    vehicle = Vehicle(
        plate_number=format_plate_display(plate_compact),
        vehicle_type=vehicle_type,
        user_category="Visitor",
        member_id=None,
    )
    db.add(vehicle)
    db.flush()
    return vehicle
