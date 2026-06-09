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
