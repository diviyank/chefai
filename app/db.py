from typing import Iterator
from sqlmodel import SQLModel, create_engine, Session
from .config import DB_PATH

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{DB_PATH}",
            connect_args={"check_same_thread": False},
        )
    return _engine


def _ensure_settings_columns(engine) -> None:
    """Idempotently add Settings columns introduced after a DB was first created.

    create_all() provisions missing tables but never ALTERs an existing one, so a
    pre-existing chefai.db is missing columns added later. Backfill them here so an
    already-deployed single-household DB keeps working after an upgrade."""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    if "settings" not in inspector.get_table_names():
        return
    existing = {col["name"] for col in inspector.get_columns("settings")}
    if "use_llm_directly" not in existing:
        with engine.begin() as conn:
            conn.execute(text(
                "ALTER TABLE settings ADD COLUMN use_llm_directly BOOLEAN NOT NULL DEFAULT 1"))


def init_db() -> None:
    import app.models  # noqa: F401  (register tables)
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    _ensure_settings_columns(engine)


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
