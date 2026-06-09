from app.models import ShoppingItem, PantryItem
from sqlmodel import select


def test_shopping_page(client):
    assert client.get("/shopping").status_code == 200


def test_add_manual_item(client, session):
    client.post("/shopping/add", data={"name": "Pommes", "qty_text": "1 kg",
                                        "store_type": "Primeur"})
    items = session.exec(select(ShoppingItem)).all()
    assert any(i.name == "Pommes" for i in items)


def test_check_item_moves_to_pantry(client, session):
    session.add(ShoppingItem(name="Lait", qty_text="1 l", store_type="Épicerie / Supermarché"))
    session.commit()
    item = session.exec(select(ShoppingItem).where(ShoppingItem.name == "Lait")).one()
    r = client.post(f"/shopping/{item.id}/check")
    assert r.status_code == 200
    session.refresh(item)
    assert item.checked is True
    assert session.exec(select(PantryItem).where(PantryItem.name == "Lait")).first() is not None


def test_shop_mode_groups_by_store(client, session):
    session.add(ShoppingItem(name="Steak", store_type="Boucherie"))
    session.add(ShoppingItem(name="Cabillaud", store_type="Poissonnerie"))
    session.commit()
    r = client.get("/shopping/mode")
    assert "Boucherie" in r.text and "Poissonnerie" in r.text
