import pytest
from sqlmodel import SQLModel, create_engine, Session
from sqlmodel.pool import StaticPool
from fastapi.testclient import TestClient
from app.main import app
from app.db import get_session
from app import seed as seed_module


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        seed_module.seed(s)
        yield s


@pytest.fixture
def client(session):
    def _override():
        yield session
    app.dependency_overrides[get_session] = _override
    # Also override get_engine so jobs use the test database
    from app import db as db_module
    test_engine = session.get_bind()
    original_get_engine = db_module.get_engine
    original_engine = db_module._engine
    db_module._engine = test_engine
    db_module.get_engine = lambda: test_engine
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        db_module.get_engine = original_get_engine
        db_module._engine = original_engine


@pytest.fixture
def fake_llm(monkeypatch):
    from app import llm_client, jobs
    state = {"reply": "", "prompts": []}

    def _complete(prompt, **kw):
        state["prompts"].append(prompt)
        if isinstance(state["reply"], Exception):
            raise state["reply"]
        return state["reply"]

    monkeypatch.setattr(llm_client, "is_configured", lambda: True)
    monkeypatch.setattr(llm_client, "complete", _complete)
    # run background work inline so the POST response already reflects the result
    monkeypatch.setattr(jobs, "_spawn", lambda job_id, work: jobs._run(job_id, work))
    return state
