from app.models import PlanningSession, Meal, ShoppingItem
from sqlmodel import select

PLAN_JSON = '''```json
{"plans":[
 {"label":"A","days":[{"day":1,"meals":[{"slot":"diner","title":"Curry","ingredients":["riz","lentilles"]}]}],
  "shopping_list":[{"name":"Riz","qty":"500 g","store_type":"Épicerie / Supermarché"}]},
 {"label":"B","days":[{"day":1,"meals":[{"slot":"diner","title":"Soupe","ingredients":["carottes"]}]}],"shopping_list":[]},
 {"label":"C","days":[{"day":1,"meals":[{"slot":"diner","title":"Pâtes","ingredients":["pâtes"]}]}],"shopping_list":[]}
]}
```'''


def test_plan_generate_prompt(client):
    r = client.post("/plan/generate", data={"n_days": "3", "lunch": "on", "dinner": "on",
                                             "leftovers": "on", "servings": "2", "cravings": ""})
    assert r.status_code == 200
    assert "plans" in r.text.lower()


def test_paste_back_stores_three_proposals(client, session):
    r = client.post("/plan/parse", data={"raw": PLAN_JSON})
    assert r.status_code == 200
    ps = session.exec(select(PlanningSession)).all()
    assert len(ps) == 1 and len(ps[0].proposals_json) == 3


def test_paste_back_bad_input_shows_error(client):
    r = client.post("/plan/parse", data={"raw": "pas de json"})
    assert "réponse non reconnue" in r.text.lower()


def test_validate_materializes_meals_and_shopping(client, session):
    client.post("/plan/parse", data={"raw": PLAN_JSON})
    ps = session.exec(select(PlanningSession)).first()
    r = client.post(f"/plan/{ps.id}/validate", data={"choice": "0"})
    assert r.status_code in (200, 303)
    session.refresh(ps)
    assert ps.status == "validated"
    assert len(session.exec(select(Meal)).all()) == 1
    assert len(session.exec(select(ShoppingItem)).all()) == 1


def test_cancel_plan(client, session):
    client.post("/plan/parse", data={"raw": PLAN_JSON})
    ps = session.exec(select(PlanningSession)).first()
    client.post(f"/plan/{ps.id}/cancel")
    session.refresh(ps)
    assert ps.status == "cancelled"


def test_meal_cooking_prompt(client, session):
    client.post("/plan/parse", data={"raw": PLAN_JSON})
    ps = session.exec(select(PlanningSession)).first()
    client.post(f"/plan/{ps.id}/validate", data={"choice": "0"})
    meal = session.exec(select(Meal)).first()
    r = client.get(f"/plan/meal/{meal.id}/prompt")
    assert "Curry" in r.text
