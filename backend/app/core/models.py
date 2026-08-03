from sqlalchemy import (
    BigInteger, 
    Column, 
    Date, 
    DateTime,
    Enum, 
    Float, 
    ForeignKey, 
    Index, 
    Integer,
    JSON, 
    String, 
    Time, 
    UniqueConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base

# Enum initialization 
plant_enum = Enum('west', 'east', 'eastwest', name='plant_location_enum')
category_enum = Enum('Employee', 'Vendor', 'Visitor', name='user_category_enum')
role_enum = Enum('Admin', 'Security', name='user_role_enum')

class Member(Base):
    __tablename__ = "member"

    # Attributes
    member_id = Column(BigInteger, primary_key=True, autoincrement=True)
    kpk_number = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    registered_plant = Column(plant_enum, nullable=False, default='west')
    category = Column(category_enum, nullable=False, default='Employee')
    sim_exp = Column(Date, nullable=True)
    location = Column(String(255), nullable=True) 
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    vehicles = relationship("Vehicle", back_populates="member")
    def __repr__(self):
        return f"Member {self.kpk_number} - {self.name}"


    def to_member_dict(self) -> dict:
        """
        converting member object data along with its data relationships into a Python dictionary
        """
        v1 = self.vehicles[0] if self.vehicles else None
        v2 = self.vehicles[1] if len(self.vehicles) > 1 else None
        sessions = sorted(
            self.vehicles[0].sessions if v1 else [],
            key=lambda s: s.entry_time,
            reverse=True,
        ) if v1 else []
        last_in_session = next((s for s in sessions if s.status == 'IN'), None)
        last_out_session = next((s for s in sessions if s.status == 'OUT'), None)

        return {
            'member_id': self.member_id,
            'kpk_number': self.kpk_number,
            'name': self.name,
            'registered_plant': self.registered_plant,
            'category': self.category,
            'location': self.location,
            'sim_exp': self.sim_exp.isoformat() if self.sim_exp else '',
            'plate_1': v1.plate_number if v1 else '',
            'vehicle_type_1': v1.vehicle_type if v1 else '',
            'stnk_exp_1': v1.stnk_exp.isoformat() if (v1 and v1.stnk_exp) else '',
            'plate_2': v2.plate_number if v2 else None,
            'vehicle_type_2': v2.vehicle_type if v2 else None,
            'position': 'IN' if (v1 and any(s.status == 'IN' for s in (v1.sessions or []))) else 'OUT',
            'last_in': last_in_session.entry_time.strftime('%Y-%m-%d %H:%M') if last_in_session else '—',
            'last_out': last_out_session.exit_time.strftime('%Y-%m-%d %H:%M') if (last_out_session and last_out_session.exit_time) else '—',
        }


class AdminUser(Base):
    __tablename__ = "admin_user"

    # Attributes
    admin_id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(role_enum, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    location = Column(plant_enum, nullable=True)

    # Relationships
    entry_exit_logs = relationship("EntryExitLog", back_populates="admin")
    def __repr__(self):
        return f"AdminUser {self.username} [{self.role}]"


class ParkingZone(Base):
    __tablename__ = "parking_zone"

    # Attributes
    zone_id = Column(BigInteger, primary_key=True, autoincrement=True)
    zone_key = Column(String(50), unique=True, nullable=False)
    zone_name = Column(String(255), nullable=False)
    total_capacity = Column(Integer, nullable=False, default=0)
    employee_capacity = Column(Integer, nullable=False, default=0)
    vendor_capacity = Column(Integer, nullable=False, default=0)
    visitor_capacity = Column(Integer, nullable=False, default=0)
    used_capacity = Column(Integer, nullable=False, default=0)
    employee_used = Column(Integer, nullable=False, default=0)
    vendor_used = Column(Integer, nullable=False, default=0)
    visitor_used = Column(Integer, nullable=False, default=0)
    camera_ids = Column(JSON, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    slots = relationship("ParkingSlot", back_populates="zone", cascade="all, delete-orphan")
    sessions = relationship("ParkingSession", back_populates="zone")
    entry_exit_logs = relationship("EntryExitLog", back_populates="zone")
    occupancy_snapshots = relationship("OccupancySnapshot", back_populates="zone")
    analytics_data = relationship("AnalyticsData", back_populates="zone")

    # Calculating the remaining available slots for each category
    @property
    def employee_available(self) -> int:
        return max(0, self.employee_capacity - self.employee_used)

    @property
    def vendor_available(self) -> int:
        return max(0, self.vendor_capacity - self.vendor_used)

    @property
    def visitor_available(self) -> int:
        return max(0, self.visitor_capacity - self.visitor_used)

    # Calculating the total occupancy rate of the entire parking area
    @property
    def overall_rate_pct(self) -> float:
        if self.total_capacity == 0:
            return 0.0
        return round(self.used_capacity / self.total_capacity * 100, 1)

    def to_dashboard_dict(self) -> dict:
        """
        Aggregates all real-time data from the parking area and converts it into a Python dictionary format
        """
        employee = {
            "used": self.employee_used,
            "total": self.employee_capacity,
            "available": self.employee_available,
            "rate_pct": round(self.employee_used / self.employee_capacity * 100, 1) if self.employee_capacity else 0.0,
        }
        vendor = {
            "used": self.vendor_used,
            "total": self.vendor_capacity,
            "available": self.vendor_available,
            "rate_pct": round(self.vendor_used / self.vendor_capacity * 100, 1) if self.vendor_capacity else 0.0,
        }
        visitor = {
            "used": self.visitor_used,
            "total": self.visitor_capacity,
            "available": self.visitor_available,
            "rate_pct": round(self.visitor_used / self.visitor_capacity * 100, 1) if self.visitor_capacity else 0.0,
        }
        return {
            "zone": self.zone_key,
            "zone_name": self.zone_name,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            # Nested form kept for the /slots/live consumer (keyed by category name).
            "category_summary": {
                "Employee": employee,
                "Vendor": vendor,
                "Visitor": visitor,
            },
            # Flat form for the /forecast/zones consumer (matches the frontend's
            # ZoneCapacity type: { employee, vendor, visitor }).
            "employee": {k: v for k, v in employee.items() if k != "rate_pct"},
            "vendor": {k: v for k, v in vendor.items() if k != "rate_pct"},
            "visitor": {k: v for k, v in visitor.items() if k != "rate_pct"},
            "total_capacity": self.total_capacity,
            "total_occupied": self.used_capacity,
            "total_available": self.total_capacity - self.used_capacity,
            "overall_rate_pct": self.overall_rate_pct,
        }

    def __repr__(self):
        return f"ParkingZone {self.zone_key} - {self.used_capacity}/{self.total_capacity}"


class ParkingSlot(Base):
    __tablename__ = "parking_slot"
    __table_args__ = (
        UniqueConstraint("zone_id", "slot_label", name="uq_slot_label_zone"),
    )

    # Attributes
    slot_id = Column(BigInteger, primary_key=True, autoincrement=True)
    zone_id = Column(BigInteger, ForeignKey("parking_zone.zone_id", ondelete="CASCADE"), nullable=False)
    slot_label = Column(String(50), nullable=False)
    category = Column(category_enum, nullable=False, default="Employee")
    coordinates_polygon = Column(JSON, nullable=False)
    current_status = Column(Enum("Available", "Occupied", name="slot_status_enum"), nullable=False, default="Available")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    zone = relationship("ParkingZone", back_populates="slots")
    def __repr__(self):
        return f"ParkingSlot {self.slot_label}: [{self.current_status}]"


class Vehicle(Base):
    __tablename__ = "vehicle"

    # Attributes
    vehicle_id = Column(BigInteger, primary_key=True, autoincrement=True)
    member_id = Column(BigInteger, ForeignKey("member.member_id", ondelete="SET NULL"), nullable=True)
    plate_number = Column(String(20), unique=True, nullable=False, index=True)
    vehicle_type = Column(String(50), nullable=False)
    user_category = Column(Enum("Member", "Visitor", name="vehicle_user_category_enum"), nullable=False)
    stnk_exp = Column(Date, nullable=True)

    # Relationships
    member = relationship("Member", back_populates="vehicles")
    sessions = relationship("ParkingSession", back_populates="vehicle")
    def __repr__(self):
        return f"Vehicle {self.plate_number}: [{self.vehicle_type}]"


class ParkingSession(Base):
    __tablename__ = "parking_session"

    # Attributes
    session_id = Column(BigInteger, primary_key=True, autoincrement=True)
    vehicle_id = Column(BigInteger, ForeignKey("vehicle.vehicle_id"), nullable=False)
    zone_id = Column(BigInteger, ForeignKey("parking_zone.zone_id"), nullable=False)
    entry_time = Column(DateTime, nullable=False, server_default=func.now())
    exit_time = Column(DateTime, nullable=True)
    booking_reference = Column(String(255), nullable=True)
    status = Column(Enum("IN", "OUT", name="session_status_enum"), nullable=False, default="IN")

    # Relationships
    vehicle = relationship("Vehicle", back_populates="sessions")
    zone = relationship("ParkingZone", back_populates="sessions")
    entry_exit_logs = relationship("EntryExitLog", back_populates="session")
    def __repr__(self):
        return f"ParkingSession {self.session_id}: [{self.status}]"


class EntryExitLog(Base):
    __tablename__ = "entry_exit_log"
    __table_args__ = (
        Index("idx_log_timestamp", "event_timestamp"),
        Index("idx_log_plate", "plate_detected"),
    )

    # Attributes
    log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(BigInteger, ForeignKey("parking_session.session_id", ondelete="SET NULL"), nullable=True)
    admin_id = Column(BigInteger, ForeignKey("admin_user.admin_id", ondelete="SET NULL"), nullable=True)
    zone_id = Column(BigInteger, ForeignKey("parking_zone.zone_id"), nullable=False)
    event_type = Column(Enum("Entry", "Exit", "Denied", name="event_type_enum"), nullable=False)
    plate_detected = Column(String(20), nullable=False)
    confidence_score = Column(Float, nullable=True)
    event_timestamp = Column(DateTime, nullable=False, server_default=func.now())
    auth_method = Column(Enum("AI_LPR", "KPK_Scan", "Manual_Security", name="auth_method_enum"), nullable=False)

    # Relationships
    session = relationship("ParkingSession", back_populates="entry_exit_logs")
    admin = relationship("AdminUser", back_populates="entry_exit_logs")
    zone = relationship("ParkingZone", back_populates="entry_exit_logs")

    def to_log_dict(self, member=None, zone_key: str = '') -> dict:
        """
        converting vehicle entry/exit activity log data into a Python dictionary format
        """
        return {
            'log_id': self.log_id,
            'plate_detected': self.plate_detected,
            'plate': self.plate_detected,
            'confidence': self.confidence_score,
            'confidence_score': self.confidence_score or 0.0,
            'conf_pct': f'{self.confidence_score * 100:.0f}%' if self.confidence_score else '—',
            'event_type': self.event_type,
            'time_scan': self.event_timestamp.strftime('%H:%M:%S') if self.event_timestamp else '',
            'timestamp': self.event_timestamp.strftime('%H:%M') if self.event_timestamp else '',
            'timestamp_full': self.event_timestamp.isoformat() if self.event_timestamp else '',
            'auth_method': self.auth_method,
            'zone': zone_key,
            'name': member.name if member else 'Unknown',
            'kpk': member.kpk_number if member else '—',
            'category': member.category if member else 'Visitor',
        }

    def __repr__(self):
        return f"EntryExitLog {self.plate_detected} [{self.event_type}]"


class OccupancySnapshot(Base):
    __tablename__ = "occupancy_snapshot"
    __table_args__ = (
        Index("idx_snapshot_zone_time", "zone_id", "recorded_at"),
    )

    # Attributes
    snapshot_id = Column(BigInteger, primary_key=True, autoincrement=True)
    zone_id = Column(BigInteger, ForeignKey("parking_zone.zone_id"), nullable=False)
    recorded_at = Column(DateTime, nullable=False)
    total_capacity = Column(Integer, nullable=False)
    total_occupied = Column(Integer, nullable=False)
    total_available = Column(Integer, nullable=False)
    overall_rate_pct = Column(Float, nullable=False)
    employee_used = Column(Integer, nullable=False, default=0)
    employee_total = Column(Integer, nullable=False, default=0)
    vendor_used = Column(Integer, nullable=False, default=0)
    vendor_total = Column(Integer, nullable=False, default=0)
    visitor_used = Column(Integer, nullable=False, default=0)
    visitor_total = Column(Integer, nullable=False, default=0)

    # Relationships
    zone = relationship("ParkingZone", back_populates="occupancy_snapshots")
    def __repr__(self):
        return f"OccupancySnapshot zone={self.zone_id} {self.recorded_at}"


class AnalyticsData(Base):
    """
    Holds BOTH the original per-zone/per-day analytics rows (legacy
    Analytics dashboard, `area_code` / `period_type` left at their
    defaults) AND the Predictive Analytics forecast rows (daily / weekly
    / monthly, one row per area code e.g. P1W..P3E).

    Reusing this single table (instead of three extra `daily_forecast`,
    `weekly_forecast`, `monthly_forecast` tables) keeps the schema at the
    original 9 tables — only a handful of nullable columns were added.
    See `app/features/forecast/models.py` for how forecast rows are
    grouped back into daily/weekly/monthly "records" for the API.
    """
    __tablename__ = "analytics_data"
    __table_args__ = (
        UniqueConstraint(
            "zone_id", "record_date", "period_type", "area_code",
            name="uq_analytics_zone_date_area",
        ),
        Index("idx_analytics_date", "record_date"),
        Index("idx_analytics_period_area", "period_type", "area_code"),
    )

    # Attributes
    analytics_id = Column(BigInteger, primary_key=True, autoincrement=True)
    zone_id = Column(BigInteger, ForeignKey("parking_zone.zone_id"), nullable=False)
    record_date = Column(Date, nullable=False)
    peak_hour_start = Column(Time, nullable=False)
    peak_hour_end = Column(Time, nullable=False)
    avg_occupancy_rate = Column(Float, nullable=False)
    predicted_demand = Column(Integer, nullable=False)
    predicted_employee = Column(Integer, nullable=False, default=0)
    predicted_vendor = Column(Integer, nullable=False, default=0)
    predicted_visitor = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    # --- Predictive Analytics (forecast) columns -------------------------
    # 'daily' (default, matches legacy rows) | 'weekly' | 'monthly'
    period_type = Column(String(10), nullable=False, default="daily", server_default="daily")
    # Area code e.g. 'P1W'..'P3E'. NULL = legacy per-zone analytics row.
    area_code = Column(String(10), nullable=True)
    # Human-readable period key: weekly -> "2026-W23", monthly -> "2026-06".
    # Left NULL for daily rows (record_date is already unambiguous).
    period_label = Column(String(20), nullable=True)
    # Predicted *available* slots for the area/period (forecast rows only).
    predicted_available = Column(Integer, nullable=True)
    # Forecast status: 'Normal' | 'Warning' | 'Full' (forecast rows only).
    status = Column(String(10), nullable=True, default="Normal")

    # Relationships
    zone = relationship("ParkingZone", back_populates="analytics_data")
    def __repr__(self):
        return f"AnalyticsData zone={self.zone_id} date={self.record_date}"
    