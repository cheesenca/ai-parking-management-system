"""
One-off dummy data generator: creates a Member + Vehicle row for every distinct
KPK identity found in the backfilled historical scan data (entry_exit_log rows
with auth_method='KPK_Scan'), so those real KPK numbers resolve to a believable
registered member instead of nothing. Names are randomized from a common
Indonesian name pool; plates are randomized but format-valid and unique. Not
part of the live app — run once, manually:

    cd backend
    python scripts/generate_dummy_members.py
"""
from __future__ import annotations

import argparse
import logging
import random
import string
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import func


def _bootstrap(f: str) -> None:
    p = Path(f).resolve()
    proj = None
    for parent in p.parents:
        if (parent / "requirements.txt").exists() and (parent / "app").is_dir():
            proj = parent
            break
    if proj and str(proj) not in sys.path:
        sys.path.insert(0, str(proj))


_bootstrap(__file__)

<<<<<<< HEAD
from app.core.database import SessionLocal  # noqa: E402
from app.core.models import EntryExitLog, Member, ParkingZone, Vehicle  # noqa: E402
=======
from app.db.session import SessionLocal  # noqa: E402
from app.db.models import EntryExitLog, Member, ParkingZone, Vehicle  # noqa: E402
>>>>>>> origin/master

logger = logging.getLogger(__name__)

FIRST_NAMES = [
    "Budi", "Andi", "Agus", "Dedi", "Eko", "Fajar", "Hendra", "Rudi", "Wawan", "Yusuf",
    "Bambang", "Joko", "Slamet", "Hadi", "Iwan", "Rizky", "Taufik", "Bagus", "Dimas", "Krisna",
    "Siti", "Ani", "Dewi", "Rina", "Sri", "Wati", "Yanti", "Fitri", "Indah", "Lestari",
    "Nur", "Putri", "Rahma", "Sari", "Wulandari", "Ratna", "Maya", "Diah", "Fera", "Yuni",
]
LAST_NAMES = [
    "Santoso", "Wijaya", "Setiawan", "Kurniawan", "Pratama", "Saputra", "Hidayat", "Nugroho",
    "Susanto", "Gunawan", "Purnama", "Kusuma", "Utomo", "Suryanto", "Wibowo", "Handoko",
    "Firmansyah", "Ramadhan", "Permadi", "Halim", "Wardani", "Puspita", "Anggraini", "Safitri",
]
CATEGORY_WEIGHTS = [("Employee", 0.75), ("Vendor", 0.15), ("Visitor", 0.10)]
PLATE_PREFIXES = ["B", "D", "E", "F", "L"]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate dummy Member/Vehicle rows for real backfilled KPK identities")
    ap.add_argument("--chunk-size", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--seed", type=int, default=42, help="Random seed, for reproducible dummy data")
    return ap.parse_args()


def random_name(rng: random.Random) -> str:
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def random_category(rng: random.Random) -> str:
    r = rng.random()
    cum = 0.0
    for cat, weight in CATEGORY_WEIGHTS:
        cum += weight
        if r <= cum:
            return cat
    return CATEGORY_WEIGHTS[-1][0]


def random_plate(rng: random.Random, used: set[str]) -> str:
    while True:
        prefix = rng.choice(PLATE_PREFIXES)
        number = rng.randint(1, 9999)
        suffix_len = rng.choice([2, 3])
        suffix = "".join(rng.choices(string.ascii_uppercase, k=suffix_len))
        plate = f"{prefix} {number} {suffix}"
        if plate not in used:
            used.add(plate)
            return plate


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    rng = random.Random(args.seed)

    db = SessionLocal()
    try:
        already = db.query(Member).count()
        if already > 0 and not args.force:
            raise SystemExit(
                f"{already} Member row(s) already exist. Pass --force to add more anyway "
                "(existing kpk_number values are skipped automatically either way)."
            )

        zones = {z.zone_id: z.zone_key for z in db.query(ParkingZone).all()}

        rows = (
            db.query(
                EntryExitLog.plate_detected,
                EntryExitLog.zone_id,
                func.count().label("n"),
            )
            .filter(EntryExitLog.auth_method == "KPK_Scan")
            .group_by(EntryExitLog.plate_detected, EntryExitLog.zone_id)
            .all()
        )

        # Pick each KPK's most-frequent zone as their "registered_plant"
        by_kpk: dict[str, Counter] = {}
        for plate_detected, zone_id, n in rows:
            kpk = plate_detected.replace("KPK-", "", 1)
            by_kpk.setdefault(kpk, Counter())[zone_id] += n

        existing_kpks = {k for (k,) in db.query(Member.kpk_number).all()}
        existing_plates = {p for (p,) in db.query(Vehicle.plate_number).all()}

        to_create = [kpk for kpk in by_kpk if kpk not in existing_kpks]
        logger.info(
            "%d distinct KPK identities found, %d already have a Member, %d to create",
            len(by_kpk), len(by_kpk) - len(to_create), len(to_create),
        )

        if args.dry_run:
            logger.info("Dry run — no rows written.")
            return

        created = 0
        for i in range(0, len(to_create), args.chunk_size):
            chunk = to_create[i:i + args.chunk_size]
            for kpk in chunk:
                top_zone_id = by_kpk[kpk].most_common(1)[0][0]
                registered_plant = zones.get(top_zone_id, "west")

                member = Member(
                    kpk_number=kpk,
                    name=random_name(rng),
                    registered_plant=registered_plant,
                    category=random_category(rng),
                )
                db.add(member)
                db.flush()  # get member.member_id

                db.add(Vehicle(
                    member_id=member.member_id,
                    plate_number=random_plate(rng, existing_plates),
                    vehicle_type=rng.choice(["Car", "Motorcycle"]),
                    user_category="Member",
                ))
                created += 1
            db.commit()
            logger.info("Members created: %d/%d", min(i + args.chunk_size, len(to_create)), len(to_create))

        logger.info("Done — created %d Member/Vehicle pairs from real backfilled KPK identities.", created)
    finally:
        db.close()


if __name__ == "__main__":
    main()
