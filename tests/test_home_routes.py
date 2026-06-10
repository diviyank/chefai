import json
from datetime import date, timedelta
from app import llm_client
from app.models import PantryItem, PlanningSession

def test_home_shows_expiring_items(client, session):
    soon = date.today() + timedelta(days=2)
    session.add(PantryItem(name="Épinards", category="Frigo", expiry_date=soon)); session.commit()
    r = client.get("/")
    assert r.status_code == 200
    assert "Épinards" in r.text
    assert "À consommer bientôt" in r.text

def test_use_it_up_generates_prompt(client, session):
    soon = date.today() + timedelta(days=1)
    session.add(PantryItem(name="Yaourt", category="Frigo", expiry_date=soon)); session.commit()
    r = client.post("/use-it-up")
    assert "Yaourt" in r.text


_RECIPES = json.dumps({"recipes": [
    {"title": "Gratin", "ingredients": [], "steps": []},
    {"title": "Poêlée", "ingredients": [], "steps": []},
    {"title": "Velouté", "ingredients": [], "steps": []},
]})


def test_use_it_up_direct_renders_cards(client, session, fake_llm):
    session.add(PantryItem(name="Courgette", category="Frigo",
                           expiry_date=date.today() + timedelta(days=1)))
    session.commit()
    fake_llm["reply"] = _RECIPES
    r = client.post("/use-it-up")
    assert r.status_code == 200
    assert "Gratin" in r.text and "/cookbook/save" in r.text


def test_use_it_up_fallback_on_failure(client, fake_llm):
    fake_llm["reply"] = llm_client.LLMError("boom")
    r = client.post("/use-it-up")
    assert "Copier le prompt" in r.text and "indisponible" in r.text.lower()
