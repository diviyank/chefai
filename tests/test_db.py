from app import db
from app.models import PantryItem
from sqlmodel import Session, select

def test_init_db_creates_tables(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db._engine = None  # reset memoized engine
    db.init_db()
    with Session(db.get_engine()) as s:
        s.add(PantryItem(name="Sel", category="Épices & condiments"))
        s.commit()
        rows = s.exec(select(PantryItem)).all()
        assert len(rows) == 1
