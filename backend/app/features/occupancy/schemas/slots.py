from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class SlotItem(BaseModel):
<<<<<<< HEAD
    """
    Represents a single parking slot's occupancy status
    """
=======
    """Represents a single parking slot's occupancy status"""
>>>>>>> origin/master
    id: str
    status: str            
    category: str = "Employee" 


class CategoryInfo(BaseModel):
<<<<<<< HEAD
    """
    Summary of occupancy for a specific category of parking slots
    """
=======
    """Summary of occupancy for a specific category of parking slots"""
>>>>>>> origin/master
    used: int
    total: int
    available: int
    rate_pct: float            


class ZoneUpdate(BaseModel):
<<<<<<< HEAD
    """
    Payload pushed by pipeline on every occupancy update
    """
=======
    """Payload pushed by pipeline on every occupancy update"""
>>>>>>> origin/master
    zone: str
    timestamp: str
    slots: List[SlotItem]
    category_summary: Dict[str, CategoryInfo]


class CapacityUpdate(BaseModel):
<<<<<<< HEAD
    """
    Payload for admins editing a zone's slot capacity per category
    """
    employee_capacity: Optional[int] = Field(default=None, ge=0)
    vendor_capacity: Optional[int] = Field(default=None, ge=0)
    visitor_capacity: Optional[int] = Field(default=None, ge=0)
    
=======
    """Payload for admins editing a zone's slot capacity per category"""
    employee_capacity: Optional[int] = Field(default=None, ge=0)
    vendor_capacity: Optional[int] = Field(default=None, ge=0)
    visitor_capacity: Optional[int] = Field(default=None, ge=0)


class DetectionEvent(BaseModel):
    """Payload for a single detection event"""
    zone: str
    plate: str
    status: str    
    confidence: float
    timestamp: str
>>>>>>> origin/master
