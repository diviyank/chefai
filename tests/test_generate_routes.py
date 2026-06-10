from app.models import PantryItem


def test_cook_page_has_three_segments(client):
    r = client.get("/cook")
    assert r.status_code == 200
    for label in ["Avec mes ingrédients", "Avec petites courses", "Planifier la semaine"]:
        assert label in r.text


def test_generate_have_returns_prompt_text(client, session):
    session.add(PantryItem(name="Poulet", category="Frigo", quantity_text="500 g"))
    session.commit()
    r = client.post("/cook/have", data={
        "max_time": "25", "cravings": "épicé", "servings": "2", "meal": "diner"
    })
    assert r.status_code == 200
    assert "Poulet" in r.text and "uniquement" in r.text.lower()


def test_generate_shop_includes_extra_limit(client):
    r = client.post("/cook/shop", data={
        "max_time": "30", "cravings": "", "servings": "2", "max_extra": "4"
    })
    assert "4" in r.text


def test_cook_suggestions_offer_recipe_save_box(client):
    """After getting suggestions the user can paste a chosen recipe to save + cook it."""
    have = client.post("/cook/have", data={
        "max_time": "25", "cravings": "", "servings": "2", "meal": "diner"})
    shop = client.post("/cook/shop", data={
        "max_time": "30", "cravings": "", "servings": "2", "max_extra": "4"})
    for r in (have, shop):
        assert "/cookbook/save" in r.text


import json
from app import llm_client

_THREE_RECIPES = json.dumps({"recipes": [
    {"title": "Poulet rôti", "ingredients": [{"name": "Poulet"}], "steps": [{"text": "Cuire"}]},
    {"title": "Salade verte", "ingredients": [], "steps": []},
    {"title": "Soupe", "ingredients": [], "steps": []},
]})


def test_cook_have_direct_renders_recipe_cards(client, fake_llm):
    fake_llm["reply"] = _THREE_RECIPES
    r = client.post("/cook/have", data={
        "max_time": "25", "cravings": "", "servings": "2", "meal": "diner"})
    assert r.status_code == 200
    assert "Poulet rôti" in r.text and "Salade verte" in r.text
    assert "/cookbook/save" in r.text          # per-card save
    assert "Générer d'autres" in r.text         # re-roll button


def test_cook_have_reroll_sends_seen_titles_as_exclude(client, fake_llm):
    fake_llm["reply"] = _THREE_RECIPES
    client.post("/cook/have", data={
        "max_time": "25", "cravings": "", "servings": "2", "meal": "diner",
        "exclude_titles": "Poulet rôti||Salade verte"})
    assert "Poulet rôti" in fake_llm["prompts"][-1]
    assert "ne propose pas" in fake_llm["prompts"][-1].lower()


def test_cook_have_llm_failure_falls_back_to_prompt(client, fake_llm):
    fake_llm["reply"] = llm_client.LLMError("boom")
    r = client.post("/cook/have", data={
        "max_time": "25", "cravings": "", "servings": "2", "meal": "diner"})
    assert r.status_code == 200
    assert "Copier le prompt" in r.text          # fallback prompt partial
    assert "indisponible" in r.text.lower()       # notice


def test_cook_shop_direct_renders_cards(client, fake_llm):
    fake_llm["reply"] = _THREE_RECIPES
    r = client.post("/cook/shop", data={
        "max_time": "30", "cravings": "", "servings": "2", "max_extra": "4"})
    assert "Poulet rôti" in r.text and "/cookbook/save" in r.text
