import json
from app import generation, llm_client


def test_kind_llm_has_expected_ceilings():
    assert generation.KIND_LLM["cook_have"]["max_tokens"] == 3000
    assert generation.KIND_LLM["plan"]["max_tokens"] == 4000
    assert generation.KIND_LLM["plan"]["effort"] == "medium"


def test_build_cook_work_returns_recipes(monkeypatch):
    reply = json.dumps({"recipes": [
        {"title": "Poulet", "ingredients": [], "steps": []},
        {"title": "Soupe", "ingredients": [], "steps": []},
        {"title": "Salade", "ingredients": [], "steps": []},
    ]})
    monkeypatch.setattr(llm_client, "complete", lambda prompt, **kw: reply)
    work = generation.build_cook_work("cook_have", json_prompt="X")
    out = work()
    assert [r["title"] for r in out["recipes"]] == ["Poulet", "Soupe", "Salade"]


def test_build_cook_work_forwards_cached_system_block(monkeypatch):
    seen = {}

    def fake_complete(prompt, **kw):
        seen.update(kw)
        return json.dumps({"recipes": [{"title": "X", "ingredients": [], "steps": []}]})

    monkeypatch.setattr(llm_client, "complete", fake_complete)
    generation.build_cook_work("cook_have", json_prompt="X", system="BASE CONTEXT")()
    assert seen["system"] == [
        {"type": "text", "text": "BASE CONTEXT", "cache_control": {"type": "ephemeral"}}]


def test_build_cook_work_omits_system_when_not_given(monkeypatch):
    seen = {}

    def fake_complete(prompt, **kw):
        seen.update(kw)
        return json.dumps({"recipes": [{"title": "X", "ingredients": [], "steps": []}]})

    monkeypatch.setattr(llm_client, "complete", fake_complete)
    generation.build_cook_work("cook_have", json_prompt="X")()
    assert "system" not in seen
