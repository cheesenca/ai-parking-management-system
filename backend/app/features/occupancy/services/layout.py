from __future__ import annotations

ZONE_CAMERA_DEVICE: dict[str, str] = {
    "west": "0",
    "east": "0",
    "eastwest": "0",
}


def _build_layout(prefix: str) -> list[dict]:
    """Build a default slot layout for a given prefix"""
    layout: list[dict] = []
    for row, count, category in [
        (1, 10, "Employee"),
        (2, 10, "Employee"),
        (3, 8, "Vendor"),
        (4, 5, "Visitor"),
    ]:
        layout.extend(
            {"id": f"{prefix}{row}-{col}", "category": category} for col in range(1, count + 1)
        )
    return layout

SLOT_LAYOUTS: dict[str, list[dict]] = {
    "west": _build_layout("W"),
    "east": _build_layout("E"),
}
SLOT_LAYOUTS["eastwest"] = SLOT_LAYOUTS["west"] + SLOT_LAYOUTS["east"]


def slot_category_map(layout: list[dict]) -> dict[str, str]:
    """
    Create a mapping of slot IDs to their categories from a given layout
    """
    return {s["id"]: s["category"] for s in layout}