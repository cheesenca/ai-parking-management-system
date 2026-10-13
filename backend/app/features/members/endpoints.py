from __future__ import annotations

import logging
import re
from datetime import date
from typing import List, Optional
<<<<<<< HEAD
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.models import Member, Vehicle
=======
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Member, Vehicle
from app.common.exceptions import ConflictError, NotFoundError
>>>>>>> origin/master

logger = logging.getLogger(__name__)
router = APIRouter(
    tags=["Members"],
)


class VehicleIn(BaseModel):
    plate_number: str
    vehicle_type: str = "Car"
    stnk_exp: Optional[str] = None 


class MemberCreate(BaseModel):
    kpk_number: str
    name: str
    registered_plant: str = "west"
    category: str = "Employee"
    sim_exp: Optional[str] = None
    plate_1: str
    vehicle_type_1: str = "Car"
    stnk_exp_1: Optional[str] = None
    plate_2: Optional[str] = None
    vehicle_type_2: Optional[str] = None


class MemberUpdate(BaseModel):
    name: Optional[str] = None
    registered_plant: Optional[str] = None
    category: Optional[str] = None
    sim_exp: Optional[str] = None
    plate_1: Optional[str] = None
    vehicle_type_1: Optional[str] = None
    stnk_exp_1: Optional[str] = None
    plate_2: Optional[str] = None
    vehicle_type_2: Optional[str] = None


class ImportRow(BaseModel):
    rows: List[MemberCreate]


def _normalize_plate(plate: Optional[str]) -> Optional[str]:
<<<<<<< HEAD
    """
    Normalizes a license plate 
    """
=======
    """Normalizes a license plate"""
>>>>>>> origin/master
    if plate is None:
        return None
    compact = re.sub(r"\s+", "", plate).upper()
    if not compact:
        return None

    match = re.match(r"^([A-Z]{1,2})(\d{1,4})([A-Z]{0,3})$", compact)
    if match:
        region, digits, series = match.groups()
        parts = [region, digits]
        if series:
            parts.append(series)
        return " ".join(parts)

    return compact


def _parse_date(s: Optional[str]) -> Optional[date]:
<<<<<<< HEAD
    """
    Convert an ISO-formatted date string into a Python date object
    """
=======
    """Convert an ISO-formatted date string into a Python date object"""
>>>>>>> origin/master
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


@router.get("")
def list_members(
    zone: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    sort: str = Query(default="asc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
<<<<<<< HEAD
    """
    Retrieve a paginated, sorted list of members based on zone, category, or text search filters
    """
=======
    """Retrieve a paginated, sorted list of members based on zone, category, or text search filters"""
>>>>>>> origin/master
    q = db.query(Member)
    if zone:
        q = q.filter(Member.registered_plant == zone)

    if category:
        q = q.filter(Member.category == category)

    if search:
        like = f"%{search}%"
        q = q.filter(
            Member.name.ilike(like) |
            Member.kpk_number.ilike(like) |
            Member.vehicles.any(Vehicle.plate_number.ilike(like))
        )

    total = q.count()
    order = Member.name.asc() if sort == "asc" else Member.name.desc()
    members = q.order_by(order).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [m.to_member_dict() for m in members],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", status_code=201)
def create_member(body: MemberCreate, db: Session = Depends(get_db)):
<<<<<<< HEAD
    """
    Registering new members in the database, along with their vehicle details
    """
=======
    """Registering new members in the database, along with their vehicle details"""
>>>>>>> origin/master
    plate_1 = _normalize_plate(body.plate_1)
    plate_2 = _normalize_plate(body.plate_2)

    if db.query(Member).filter(Member.kpk_number == body.kpk_number).first():
        logger.warning("Create member rejected: KPK '%s' already registered", body.kpk_number)
<<<<<<< HEAD
        raise HTTPException(status_code=409, detail=f"KPK '{body.kpk_number}' already registered")
    
    if db.query(Vehicle).filter(Vehicle.plate_number == plate_1).first():
        logger.warning("Create member rejected: plate '%s' already registered", plate_1)
        raise HTTPException(status_code=409, detail=f"Plate '{plate_1}' already registered")
=======
        raise ConflictError(f"KPK '{body.kpk_number}' already registered")
    
    if db.query(Vehicle).filter(Vehicle.plate_number == plate_1).first():
        logger.warning("Create member rejected: plate '%s' already registered", plate_1)
        raise ConflictError(f"Plate '{plate_1}' already registered")
>>>>>>> origin/master

    member = Member(
        kpk_number=body.kpk_number,
        name=body.name,
        registered_plant=body.registered_plant,
        category=body.category,
        sim_exp=_parse_date(body.sim_exp),
    )
    db.add(member)
    db.flush()  
    db.add(Vehicle(
        member_id=member.member_id,
        plate_number=plate_1,
        vehicle_type=body.vehicle_type_1,
        stnk_exp=_parse_date(body.stnk_exp_1),
        user_category="Member",
    ))

    if plate_2:
        if db.query(Vehicle).filter(Vehicle.plate_number == plate_2).first():
<<<<<<< HEAD
            raise HTTPException(status_code=409, detail=f"Plate 2 '{plate_2}' already registered")
=======
            raise ConflictError(f"Plate 2 '{plate_2}' already registered")
>>>>>>> origin/master
        db.add(Vehicle(
            member_id=member.member_id,
            plate_number=plate_2,
            vehicle_type=body.vehicle_type_2 or "Car",
            user_category="Member",
        ))

    db.commit()
    db.refresh(member)
    logger.info("Member created: kpk='%s', name='%s'", member.kpk_number, member.name)
    return member.to_member_dict()


@router.put("/{member_id}")
def update_member(member_id: int, body: MemberUpdate, db: Session = Depends(get_db)):
<<<<<<< HEAD
    """
    Update member profile data and associated vehicle data based on member_id
    """
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        logger.warning("Update member failed: member_id=%s not found", member_id)
        raise HTTPException(status_code=404, detail="Member not found")
=======
    """Update member profile data and associated vehicle data based on member_id"""
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        logger.warning("Update member failed: member_id=%s not found", member_id)
        raise NotFoundError("Member not found")
>>>>>>> origin/master

    if body.name: 
        member.name = body.name

    if body.registered_plant: 
        member.registered_plant = body.registered_plant

    if body.category: 
        member.category = body.category

    if body.sim_exp is not None:
        member.sim_exp = _parse_date(body.sim_exp)

    plate_1 = _normalize_plate(body.plate_1)
    plate_2 = _normalize_plate(body.plate_2)

    v1 = member.vehicles[0] if member.vehicles else None
    if v1 and plate_1:
        conflict = db.query(Vehicle).filter(
            Vehicle.plate_number == plate_1,
            Vehicle.vehicle_id != v1.vehicle_id,
        ).first()

        if conflict:
<<<<<<< HEAD
            raise HTTPException(status_code=409, detail=f"Plate '{plate_1}' already used by the other member")
=======
            raise ConflictError(f"Plate '{plate_1}' already used by the other member")
>>>>>>> origin/master
        v1.plate_number = plate_1

    if v1 and body.vehicle_type_1: 
        v1.vehicle_type = body.vehicle_type_1

    if v1 and body.stnk_exp_1 is not None: 
        v1.stnk_exp = _parse_date(body.stnk_exp_1)

    if plate_2:
        v2 = member.vehicles[1] if len(member.vehicles) > 1 else None
        conflict = db.query(Vehicle).filter(
            Vehicle.plate_number == plate_2,
            Vehicle.vehicle_id != (v2.vehicle_id if v2 else -1),
        ).first()
        if conflict:
<<<<<<< HEAD
            raise HTTPException(status_code=409, detail=f"Plate '{plate_2}' already used by the other member")
=======
            raise ConflictError(f"Plate '{plate_2}' already used by the other member")
>>>>>>> origin/master
        if v2:
            v2.plate_number = plate_2
            if body.vehicle_type_2: v2.vehicle_type = body.vehicle_type_2
        else:
            db.add(Vehicle(
                member_id=member.member_id,
                plate_number=plate_2,
                vehicle_type=body.vehicle_type_2 or "Car",
                user_category="Member",
            ))

    db.commit()
    db.refresh(member)
    logger.info("Member updated: member_id=%s", member_id)
    return member.to_member_dict()


@router.delete("/{member_id}", status_code=204)
def delete_member(member_id: int, db: Session = Depends(get_db)):
<<<<<<< HEAD
    """
    Delete member data based on ID
    """
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        logger.warning("Delete member failed: member_id=%s not found", member_id)
        raise HTTPException(status_code=404, detail="Member not found")
=======
    """Delete member data based on ID"""
    member = db.query(Member).filter(Member.member_id == member_id).first()
    if not member:
        logger.warning("Delete member failed: member_id=%s not found", member_id)
        raise NotFoundError("Member not found")
>>>>>>> origin/master
    db.delete(member)
    db.commit()
    logger.info("Member deleted: member_id=%s", member_id)


@router.post("/import")
def import_members(body: ImportRow, db: Session = Depends(get_db)):
<<<<<<< HEAD
    """
    Perform a bulk import of member data from a list or array
    """
=======
    """Perform a bulk import of member data from a list or array"""
>>>>>>> origin/master
    created = 0
    errors: list[str] = []
    for row in body.rows:
        try:
            plate_1 = _normalize_plate(row.plate_1)
            plate_2 = _normalize_plate(row.plate_2)

            if db.query(Member).filter(Member.kpk_number == row.kpk_number).first():
                errors.append(f"{row.kpk_number}: KPK already registered")
                continue
            if db.query(Vehicle).filter(Vehicle.plate_number == plate_1).first():
                errors.append(f"{row.kpk_number}: Plate {plate_1} already registered")
                continue
            member = Member(
                kpk_number=row.kpk_number, name=row.name,
                registered_plant=row.registered_plant, category=row.category,
                sim_exp=_parse_date(row.sim_exp),
            )
            db.add(member); db.flush()
            db.add(Vehicle(
                member_id=member.member_id, plate_number=plate_1,
                vehicle_type=row.vehicle_type_1, stnk_exp=_parse_date(row.stnk_exp_1),
                user_category="Member",
            ))
            if plate_2:
                db.add(Vehicle(
                    member_id=member.member_id, plate_number=plate_2,
                    vehicle_type=row.vehicle_type_2 or "Car", user_category="Member",
                ))
            created += 1
        except Exception as e:
            errors.append(f"{row.kpk_number}: {e}")
            logger.error("Import row failed for kpk='%s': %s", row.kpk_number, e)
            db.rollback()
    db.commit()
    logger.info("Member import finished: created=%d, errors=%d", created, len(errors))
    return {"created": created, "errors": errors}