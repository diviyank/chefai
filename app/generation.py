"""Per-kind generation wiring: LLM config, work() builders, and result rendering.
The only module that maps a `kind` to its model/tokens/thinking and result partial."""
from . import llm_client
from . import response_parser as rp

# Per-kind complete() kwargs. Recipes/plan keep adaptive thinking (reasoning helps);
# ceilings are well above structured-reply size but far below the old 8000.
KIND_LLM = {
    "cook_have": {"max_tokens": 3000},
    "cook_shop": {"max_tokens": 3000},
    "plan": {"max_tokens": 4000, "effort": "medium"},
}


def build_cook_work(kind: str, *, json_prompt: str):
    cfg = KIND_LLM[kind]

    def work() -> dict:
        parsed = rp.parse_recipe_list_response(llm_client.complete(json_prompt, **cfg))
        return {"recipes": [r.model_dump() for r in parsed.recipes]}

    return work


def build_plan_work(*, json_prompt: str, params: dict):
    cfg = KIND_LLM["plan"]

    def work() -> dict:
        parsed = rp.parse_plan_response(llm_client.complete(json_prompt, **cfg))
        from sqlmodel import Session
        from .db import get_engine
        from .models import PlanningSession
        with Session(get_engine()) as s:
            ps = PlanningSession(
                params_json=params,
                proposals_json=[p.model_dump() for p in parsed.plans],
                status="proposed")
            s.add(ps)
            s.commit()
            s.refresh(ps)
            return {"ps_id": ps.id}

    return work
