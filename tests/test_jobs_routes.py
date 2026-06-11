import json
from app.models import GenerationJob


def _add(session, **kw):
    job = GenerationJob(**kw); session.add(job); session.commit(); session.refresh(job)
    return job


def test_panel_running_shows_spinner_and_polls(client, session):
    _add(session, kind="cook_have", status="running", params_json="{}", prompt="P")
    r = client.get("/jobs/cook_have/panel")
    assert r.status_code == 200
    assert "Claude réfléchit" in r.text
    assert 'hx-trigger="every 2s"' in r.text
    assert "disabled" in r.text


def test_panel_done_renders_cards_and_stops_polling(client, session):
    _add(session, kind="cook_have", status="done", params_json="{}",
         result_json=json.dumps({"recipes": [
             {"title": "Poulet rôti", "ingredients": [], "steps": []}]}))
    r = client.get("/jobs/cook_have/panel")
    assert "Poulet rôti" in r.text
    assert 'hx-trigger="every 2s"' not in r.text     # polling stopped


def test_panel_error_renders_prompt_fallback(client, session):
    _add(session, kind="cook_have", status="error", params_json="{}",
         prompt="COPIE MOI", notice="Génération directe indisponible")
    r = client.get("/jobs/cook_have/panel")
    assert "COPIE MOI" in r.text
    assert "indisponible" in r.text.lower()


def test_cook_panel_fallback_keeps_recipe_paste_box(client, session):
    """When a direct-LLM cook job fails, the copy-paste fallback must still offer the
    paste-back box so the user can save a recipe from the LLM's reply."""
    for kind in ("cook_have", "cook_shop"):
        _add(session, kind=kind, status="error", params_json="{}",
             prompt="PROMPT", notice="Génération directe indisponible")
        r = client.get(f"/jobs/{kind}/panel")
        assert 'id="recipe-save"' in r.text, kind
        assert "Enregistrer la recette" in r.text, kind
