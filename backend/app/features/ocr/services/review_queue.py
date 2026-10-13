from __future__ import annotations

import logging
import sys
import uuid
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from app.db.session import session_local
from app.db.models import EntryExitLog, ParkingZone, PendingPlateReview
from app.features.ocr.services.plate_lookup import find_vehicle_by_plate, resolve_or_create_vehicle
from app.features.ocr.services.session_tracking import record_entry, record_exit

# Bare-module imports, same convention as ocr/api/endpoints.py — `pipeline`
# and `plate_utils` live outside any importable package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
from pipeline import CONF_THRESHOLD  # noqa: E402
from plate_utils import clean_plate_text, is_valid_plate_format, normalize_plate, preprocess_plate  # noqa: E402

logger = logging.getLogger(__name__)

CAPTURE_DIR = Path(__file__).resolve().parent.parent / "data" / "pending_captures"


def _save_crops(crops: list[np.ndarray]) -> list[str]:
    if not crops:
        return []
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for crop in crops:
        path = CAPTURE_DIR / f"{uuid.uuid4().hex}.jpg"
        if cv2.imwrite(str(path), crop):
            paths.append(str(path))
    return paths


def queue_for_review(event: dict, zone_key: str) -> int | None:
    """
    Persist a low-confidence/no-plate detection the moment it's captured, so
    it's never lost even if nobody is watching the live dashboard. Runs in
    its own short-lived session, wrapped in try/except — same reasoning as
    save_detection_event (ocr/api/endpoints.py): a failure here must never
    break the live camera loop.

    Returns the new review_id, or None if it couldn't be queued.
    """
    db = session_local()
    try:
        zone = db.query(ParkingZone).filter(ParkingZone.zone_key == zone_key).first()
        if zone is None:
            logger.warning("[ReviewQueue] Unknown zone_key '%s', skipping capture", zone_key)
            return None

        review = PendingPlateReview(
            zone_id=zone.zone_id,
            track_id=event.get('track_id'),
            plate_guess=normalize_plate(event.get('plate', '')) or None,
            confidence=event.get('confidence') or 0.0,
            vehicle_type=event.get('vehicle_type'),
            event_type=event.get('event_type'),
            image_paths=_save_crops(event.get('crops') or []),
            status='queued',
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        return review.review_id
    except Exception as e:
        db.rollback()
        logger.error("[ReviewQueue] Failed to queue detection for review: %s", e)
        return None
    finally:
        db.close()


def run_pending_review_sweep() -> None:
    """
    Scheduled job (see main.py) — attempts to auto-resolve every 'queued'
    pending review by rerunning OCR against its buffered crops (genuinely
    different frames than the one live pass already tried, not a repeat of
    the same pixels). Anything still unresolved is handed off to a human via
    status='needs_review'.
    """
    # Deferred import: ocr/api/endpoints.py imports queue_for_review from
    # this module, so importing get_pipeline at module load time here would
    # be a circular import. By call time both modules are fully loaded.
    from app.features.ocr.api.endpoints import get_pipeline

    pipeline = get_pipeline()
    if pipeline is None:
        logger.warning("[ReviewQueue] Pipeline not loaded — skipping sweep")
        return

    db = session_local()
    try:
        review_ids = [
            r.review_id for r in
            db.query(PendingPlateReview.review_id).filter(PendingPlateReview.status == 'queued').all()
        ]
    finally:
        db.close()

    if not review_ids:
        return

    logger.info("[ReviewQueue] Sweeping %d queued review(s)", len(review_ids))
    for review_id in review_ids:
        try:
            _resolve_one(review_id, pipeline)
        except Exception:
            logger.exception("[ReviewQueue] Sweep failed for review_id=%s", review_id)


def _resolve_one(review_id: int, pipeline) -> None:
    db = session_local()
    try:
        review = db.query(PendingPlateReview).filter(PendingPlateReview.review_id == review_id).first()
        if review is None or review.status != 'queued':
            return  # already handled by someone else / a prior sweep

        best_text, best_conf = '', 0.0
        for path in (review.image_paths or []):
            crop = cv2.imread(path)
            if crop is None:
                continue
            processed = preprocess_plate(crop)
            ocr_out = pipeline.ocr.readtext(processed)
            if not ocr_out:
                continue
            candidate = max(ocr_out, key=lambda x: x[2])
            text = clean_plate_text(candidate[1])
            if text and candidate[2] > best_conf:
                best_text, best_conf = text, candidate[2]

        if best_text:
            review.plate_guess = best_text
        review.confidence = max(best_conf, review.confidence or 0.0)

        if best_text and best_conf >= CONF_THRESHOLD:
            plate_norm = normalize_plate(best_text)
            vehicle = find_vehicle_by_plate(db, plate_norm)
            if vehicle is None and not is_valid_plate_format(plate_norm):
                # Same admissibility guard as the live auto-save path — an
                # unattended sweep shouldn't invent vehicle records for
                # non-standard plate text.
                review.status = 'needs_review'
                db.commit()
                return
            if vehicle is None:
                vehicle = resolve_or_create_vehicle(db, plate_norm, review.vehicle_type or "Car")

            event_type_map = {"entry": "Entry", "exit": "Exit"}
            log = EntryExitLog(
                zone_id=review.zone_id,
                event_type=event_type_map.get(review.event_type, "Denied"),
                plate_detected=plate_norm[:20],
                confidence_score=best_conf,
                event_timestamp=review.captured_at,
                auth_method="AI_LPR",
            )
            db.add(log)
            db.flush()

            if review.event_type == "entry":
                record_entry(db, vehicle.vehicle_id, review.zone_id, review.captured_at)
            elif review.event_type == "exit":
                record_exit(db, vehicle.vehicle_id, review.captured_at)

            review.status = 'auto_resolved'
            review.resulting_log_id = log.log_id
            review.resolved_at = datetime.now()
        else:
            review.status = 'needs_review'

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
