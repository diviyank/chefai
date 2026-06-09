from sqlmodel import SQLModel, create_engine, Session, select
from sqlmodel.pool import StaticPool
from app import seed
from app.models import Settings, Tool, Skill
from app.enums import DEFAULT_CATEGORIES, DEFAULT_TOOLS

def _session():
    e = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(e)
    return Session(e)

def test_seed_creates_singleton_settings_and_lists():
    with _session() as s:
        seed.seed(s)
        settings = s.get(Settings, 1)
        assert settings.language == "fr"
        assert settings.categories_json == DEFAULT_CATEGORIES
        assert len(s.exec(select(Tool)).all()) == len(DEFAULT_TOOLS)

def test_seed_is_idempotent():
    with _session() as s:
        seed.seed(s); seed.seed(s)
        assert len(s.exec(select(Skill)).all()) >= 1
        assert s.get(Settings, 1) is not None
