from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class SlotItem(BaseModel):
    """
    Represents a single parking slot's occupancy status
    """
    id: str
    status: str            
    category: str = "Employee" 


class CategoryInfo(BaseModel):
    """
    Summary of occupancy for a specific category of parking slots
    """
    used: int
    total: int
    available: int
    rate_pct: float            


class ZoneUpdate(BaseModel):
    """
    Payload pushed by pipeline on every occupancy update
    """
    zone: str
    timestamp: str
    slots: List[SlotItem]
    category_summary: Dict[str, CategoryInfo]


class CapacityUpdate(BaseModel):
    """
    Payload for admins editing a zone's slot capacity per category
    """
    employee_capacity: Optional[int] = Field(default=None, ge=0)
    vendor_capacity: Optional[int] = Field(default=None, ge=0)
    visitor_capacity: Optional[int] = Field(default=None, ge=0)
    