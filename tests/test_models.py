from datetime import date
from sqlmodel import SQLModel, create_engine, Session
from sqlmodel.pool import StaticPool
from app import models

def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    return Session(engine)

def test_pantry_item_roundtrip_with_json_and_optionals():
    with _session() as s:
        item = models.PantryItem(name="Poulet", category="Frigo", expiry_date=date(2026, 6, 20))
        s.add(item); s.commit(); s.refresh(item)
        assert item.id is not None
        assert item.quantity_text is None
        assert item.is_staple is False

def test_recipe_stores_json_lists():
    with _session() as s:
        r = models.Recipe(
            title="Curry",
            ingredients_json=[{"name": "Lentilles", "qty": "200 g"}],
            steps_json=[{"text": "Mijoter", "duration_seconds": 1200}],
            tags_json=["végétarien"],
        )
        s.add(r); s.commit(); s.refresh(r)
        assert r.steps_json[0]["duration_seconds"] == 1200
        assert r.tags_json == ["végétarien"]

def test_settings_defaults_to_copy_paste():
    """Copy-paste is the default-capable mode; direct Claude is opt-in (key + toggle)."""
    from app.models import Settings
    assert Settings().use_llm_directly is False
