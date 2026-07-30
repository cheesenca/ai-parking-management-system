from typing import Literal, Optional
from pydantic import BaseModel


class ManualApprovalRequest(BaseModel):
    """
    Payload for a staff member manually approving/correcting a low-confidence
    LPR read before it's recorded
    """
    plate: str
    zone: str
    event_type: Literal["entry", "exit"]
    timestamp: str
    original_confidence: Optional[float] = None
