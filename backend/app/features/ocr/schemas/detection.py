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
    # Set when approving from the Pending Review list (or the live modal, if
    # the detection was already queued) — links this approval back to the
    # persisted row instead of leaving it stuck at 'queued'/'needs_review'.
    review_id: Optional[int] = None
