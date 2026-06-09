from datetime import date, timedelta
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
