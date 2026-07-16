
from __future__ import annotations

from collections import defaultdict


class DirectionDetector:
    """
    Tracks vehicle centroids across frames and fires an event
    when a vehicle crosses the configured tripwire Y-coordinate.

    Usage:
        detector = DirectionDetector(tripwire_y=320)
        direction = detector.update(track_id=5, cx=300, cy=310)
        # returns 'entry', 'exit', or None
    """

    def __init__(self, tripwire_y: int, history_len: int = 30, cooldown_frames: int = 60):
        """
        tripwire_y      : Y pixel coordinate of the gate line in the frame.
                          Set this by looking at your camera feed —
                          it should be the midpoint of the gate opening.
        history_len     : How many past centroid positions to remember per track.
        cooldown_frames : Frames to wait before allowing the same track ID
                          to trigger another event (prevents double-counting).
        """
        self.tripwire_y      = tripwire_y
        self.history_len     = history_len
        self.cooldown_frames = cooldown_frames

        self._histories : dict[int, list[tuple[float, float]]] = defaultdict(list)
        self._crossed   : dict[int, int] = {}   # track_id → frame_number when crossed
        self._frame_num : int = 0

    def update(self, track_id: int, cx: float, cy: float) -> str | None:
        """
        Call once per detected vehicle per frame.
        Returns 'entry', 'exit', or None.
        """
        self._frame_num += 1

        history = self._histories[track_id]
        history.append((cx, cy))
        if len(history) > self.history_len:
            history.pop(0)

        # Need at least 2 points to determine direction
        if len(history) < 2:
            return None

        # Respect cooldown — don't fire twice for same vehicle
        last_cross = self._crossed.get(track_id)
        if last_cross and (self._frame_num - last_cross) < self.cooldown_frames:
            return None

        prev_y = history[-2][1]
        curr_y = history[-1][1]

        crossed = self._check_crossing(prev_y, curr_y)
        if crossed:
            self._crossed[track_id] = self._frame_num

        return crossed

    def _check_crossing(self, prev_y: float, curr_y: float) -> str | None:
        twy = self.tripwire_y
        if prev_y < twy and curr_y >= twy:
            return 'entry'   # top → bottom = moving into parking lot
        if prev_y >= twy and curr_y < twy:
            return 'exit'    # bottom → top = leaving parking lot
        return None

    def is_near_tripwire(self, cy: float, margin: int = 80) -> bool:
        """
        Returns True when a vehicle centroid is within `margin` pixels
        of the tripwire — this is when we trigger OCR.
        """
        return abs(cy - self.tripwire_y) < margin

    def get_trail(self, track_id: int) -> list[tuple[float, float]]:
        """Returns the stored centroid trail for drawing on frame."""
        return self._histories.get(track_id, [])

    def cleanup_lost_tracks(self, active_ids: set[int]):
        """Remove history for tracks that are no longer detected."""
        stale = set(self._histories.keys()) - active_ids
        for tid in stale:
            del self._histories[tid]
