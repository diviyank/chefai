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


def _legacy_settings_engine():
    """An in-memory SQLite engine with a 'settings' table that predates the
    use_llm_directly column (simulates an already-deployed chefai.db)."""
    from sqlalchemy import create_engine, text
    from sqlmodel.pool import StaticPool
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE settings (id INTEGER PRIMARY KEY, household_size INTEGER)"))
    return engine


def test_ensure_settings_columns_backfills_use_llm_directly():
    from sqlalchemy import inspect
    from app.db import _ensure_settings_columns
    engine = _legacy_settings_engine()
    _ensure_settings_columns(engine)
    cols = {c["name"] for c in inspect(engine).get_columns("settings")}
    assert "use_llm_directly" in cols


def test_ensure_settings_columns_is_idempotent():
    from sqlalchemy import inspect
    from app.db import _ensure_settings_columns
    engine = _legacy_settings_engine()
    _ensure_settings_columns(engine)
    _ensure_settings_columns(engine)  # second call must not raise (column already present)
    cols = {c["name"] for c in inspect(engine).get_columns("settings")}
    assert "use_llm_directly" in cols


def test_ensure_settings_columns_safe_when_table_absent():
    from sqlalchemy import create_engine
    from sqlmodel.pool import StaticPool
    from app.db import _ensure_settings_columns
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    _ensure_settings_columns(engine)  # no 'settings' table yet -> must be a no-op, no error
