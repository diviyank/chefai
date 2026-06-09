from app.models import PantryItem
from sqlmodel import select


def test_pantry_page_renders(client):
    assert client.get("/pantry").status_code == 200


def test_add_item_minimal_name_only(client, session):
    r = client.post("/pantry/add", data={"name": "Tomates", "category": "Fruits & légumes",
                                          "quantity_text": "", "expiry_date": ""})
    assert r.status_code == 200
    items = session.exec(select(PantryItem)).all()
    assert any(i.name == "Tomates" for i in items)


def test_spice_category_defaults_to_staple(client, session):
    client.post("/pantry/add", data={"name": "Paprika", "category": "Épices & condiments",
                                      "quantity_text": "", "expiry_date": ""})
    item = session.exec(select(PantryItem).where(PantryItem.name == "Paprika")).one()
    assert item.is_staple is True


def test_delete_item(client, session):
    client.post("/pantry/add", data={"name": "Lait", "category": "Frigo",
                                      "quantity_text": "", "expiry_date": ""})
    item = session.exec(select(PantryItem).where(PantryItem.name == "Lait")).one()
    r = client.delete(f"/pantry/{item.id}")
    assert r.status_code == 200
    assert session.get(PantryItem, item.id) is None
