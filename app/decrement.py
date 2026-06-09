import re
import unicodedata
from typing import Optional

_NUM_UNIT_RE = re.compile(r"^\s*([0-9]+(?:[.,][0-9]+)?)\s*([a-zA-Zàâéèêg]*)\s*$")


def normalize_name(name: str) -> str:
    if not name:
        return ""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = text.lower().strip()
    if text.endswith("s") and len(text) > 3:
        text = text[:-1]
    return text


def parse_quantity(text: Optional[str]):
    """Return (number, unit) or None when not a clean numeric quantity."""
    if not text:
        return None
    m = _NUM_UNIT_RE.match(text)
    if not m:
        return None
    number = float(m.group(1).replace(",", "."))
    unit = m.group(2).lower()
    return (number, unit)


def _format_qty(number: float, unit: str) -> str:
    number = round(number, 2)
    if number == int(number):
        number = int(number)
    return f"{number} {unit}".strip()


def compute_decrement(pantry_items: list[dict], recipe_ingredients: list[dict]) -> list[dict]:
    """Match recipe ingredients to pantry items and propose changes.

    Each proposal: {pantry_item_id, name, action, new_quantity_text|None}
    action ∈ {"subtract", "remove", "confirm"}.
    Staples and unmatched ingredients are excluded.
    """
    by_name = {}
    for item in pantry_items:
        if item.get("is_staple"):
            continue
        by_name[normalize_name(item["name"])] = item

    proposals = []
    for ing in recipe_ingredients:
        key = normalize_name(ing.get("name", ""))
        item = by_name.get(key)
        if item is None:
            continue
        pantry_q = parse_quantity(item.get("quantity_text"))
        recipe_q = parse_quantity(ing.get("qty"))
        if pantry_q and recipe_q and pantry_q[1] == recipe_q[1]:
            remaining = pantry_q[0] - recipe_q[0]
            if remaining > 0:
                proposals.append({
                    "pantry_item_id": item["id"], "name": item["name"],
                    "action": "subtract",
                    "new_quantity_text": _format_qty(remaining, pantry_q[1]),
                })
            else:
                proposals.append({
                    "pantry_item_id": item["id"], "name": item["name"],
                    "action": "remove", "new_quantity_text": None,
                })
        else:
            proposals.append({
                "pantry_item_id": item["id"], "name": item["name"],
                "action": "confirm", "new_quantity_text": item.get("quantity_text"),
            })
    return proposals
