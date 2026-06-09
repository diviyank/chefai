from app.models import Recipe, PantryItem
from sqlmodel import select

RECIPE_JSON = '''```json
{"title":"Omelette","ingredients":[{"name":"Oeufs","qty":"3"}],
 "steps":[{"text":"Battre les oeufs","duration_seconds":60},{"text":"Cuire"}],"tags":["rapide"]}
```'''

def test_cookbook_page(client):
    assert client.get("/cookbook").status_code == 200

def test_save_recipe_from_paste(client, session):
    r = client.post("/cookbook/save", data={"raw": RECIPE_JSON})
    assert r.status_code in (200, 303)
    recipes = session.exec(select(Recipe)).all()
    assert recipes[0].title == "Omelette"
    assert recipes[0].steps_json[0]["duration_seconds"] == 60

def test_save_recipe_bad_input_shows_error(client):
    r = client.post("/cookbook/save", data={"raw": "rien"})
    assert "réponse non reconnue" in r.text.lower()

def test_htmx_save_returns_inline_success_with_cook_link(client, session):
    """Saving from the cook page (HTMX) stays inline and links straight into cook mode."""
    r = client.post("/cookbook/save", data={"raw": RECIPE_JSON},
                    headers={"HX-Request": "true"})
    assert r.status_code == 200
    recipe = session.exec(select(Recipe)).one()
    assert recipe.title == "Omelette"
    assert f"/cookbook/{recipe.id}/cook" in r.text  # one-tap into cooking mode

def test_htmx_save_success_replaces_form_to_prevent_duplicates(client):
    """On success the paste form is gone (replaced by confirmation) so it can't be re-submitted."""
    r = client.post("/cookbook/save", data={"raw": RECIPE_JSON},
                    headers={"HX-Request": "true"})
    assert 'name="raw"' not in r.text  # no lingering textarea to resubmit
    assert "enregistr" in r.text.lower()  # explicit confirmation

def test_htmx_save_bad_input_shows_error_inline(client):
    r = client.post("/cookbook/save", data={"raw": "rien"},
                    headers={"HX-Request": "true"})
    assert "réponse non reconnue" in r.text.lower()
    assert 'name="raw"' in r.text  # form re-rendered so the user can fix and retry

def test_delete_recipe_removes_it(client, session):
    client.post("/cookbook/save", data={"raw": RECIPE_JSON})
    recipe = session.exec(select(Recipe)).one()
    r = client.post(f"/cookbook/{recipe.id}/delete", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert session.get(Recipe, recipe.id) is None

def test_cookbook_search_filters_by_title(client, session):
    client.post("/cookbook/save", data={"raw": RECIPE_JSON})  # Omelette
    other = RECIPE_JSON.replace("Omelette", "Soupe de poireaux")
    client.post("/cookbook/save", data={"raw": other})
    r = client.get("/cookbook/search", params={"q": "soupe"})
    assert "Soupe de poireaux" in r.text
    assert "Omelette" not in r.text

def test_cookbook_page_has_search_bar(client):
    r = client.get("/cookbook")
    assert "/cookbook/search" in r.text

def test_cook_mode_lists_steps(client, session):
    client.post("/cookbook/save", data={"raw": RECIPE_JSON})
    recipe = session.exec(select(Recipe)).first()
    r = client.get(f"/cookbook/{recipe.id}/cook")
    assert "Battre les oeufs" in r.text

def test_decrement_review_proposes_changes(client, session):
    session.add(PantryItem(name="Oeufs", category="Frigo", quantity_text="6")); session.commit()
    client.post("/cookbook/save", data={"raw": RECIPE_JSON})
    recipe = session.exec(select(Recipe)).first()
    r = client.get(f"/cookbook/{recipe.id}/finish")
    assert "Oeufs" in r.text and "Mettre à jour" in r.text

def test_apply_decrement_updates_pantry(client, session):
    session.add(PantryItem(name="Oeufs", category="Frigo", quantity_text="6")); session.commit()
    client.post("/cookbook/save", data={"raw": RECIPE_JSON})
    recipe = session.exec(select(Recipe)).first()
    item = session.exec(select(PantryItem).where(PantryItem.name == "Oeufs")).one()
    r = client.post("/cookbook/decrement/apply",
                    data={f"action_{item.id}": "subtract", f"qty_{item.id}": "3"})
    assert r.status_code in (200, 303)
    session.refresh(item)
    assert item.quantity_text == "3"
