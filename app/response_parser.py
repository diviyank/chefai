import json
import re
from pydantic import ValidationError
from .schemas import PlanResponse, RecipeResponse, ShoppingResponse

_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)

ERROR_MSG = (
    "Réponse non reconnue — vérifiez que vous avez copié le bloc complet "
    "renvoyé par l'IA (le bloc ```json ... ```)."
)


class ParseError(ValueError):
    pass


def extract_json_block(text: str) -> dict:
    """Lenient: prefer a fenced ```json block, else the widest {...} span."""
    if not text or not text.strip():
        raise ParseError(ERROR_MSG)
    m = _FENCE_RE.search(text)
    candidate = m.group(1) if m else None
    if candidate is None:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start:end + 1]
    if candidate is None:
        raise ParseError(ERROR_MSG)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ParseError(ERROR_MSG) from exc


def _parse(text: str, model):
    data = extract_json_block(text)
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise ParseError(ERROR_MSG) from exc


def parse_plan_response(text: str) -> PlanResponse:
    parsed = _parse(text, PlanResponse)
    if not parsed.plans:
        raise ParseError(ERROR_MSG)
    return parsed


def parse_recipe_response(text: str) -> RecipeResponse:
    return _parse(text, RecipeResponse)


def parse_shopping_response(text: str) -> ShoppingResponse:
    return _parse(text, ShoppingResponse)
