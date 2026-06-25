from pydantic import BaseModel
from typing import List, Dict

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


class DetectionEvent(BaseModel):
    """
    Pushed once per vehicle detection by pipeline
    """
    zone: str
    timestamp: str
    plate: str
    confidence: float          
    status: str = "Occupied"  