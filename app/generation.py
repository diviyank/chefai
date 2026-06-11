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


def _llm_kwargs(kind: str, system: str | None) -> dict:
    """Per-kind complete() kwargs, optionally with the stable base context sent as a
    cached system block. Caching is best-effort: Sonnet 4.6 only caches prefixes above
    ~2048 tokens, so for small base contexts this is a silent no-op (verify via
    usage.cache_read_input_tokens). It never changes the produced output."""
    kw = dict(KIND_LLM[kind])
    if system:
        kw["system"] = [{"type": "text", "text": system,
                         "cache_control": {"type": "ephemeral"}}]
    return kw


def build_cook_work(kind: str, *, json_prompt: str, system: str | None = None):
    kw = _llm_kwargs(kind, system)

    def work() -> dict:
        parsed = rp.parse_recipe_list_response(llm_client.complete(json_prompt, **kw))
        return {"recipes": [r.model_dump() for r in parsed.recipes]}

    return work


def build_plan_work(*, json_prompt: str, params: dict, system: str | None = None):
    kw = _llm_kwargs("plan", system)

    def work() -> dict:
        parsed = rp.parse_plan_response(llm_client.complete(json_prompt, **kw))
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
