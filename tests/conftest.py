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
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def fake_llm(monkeypatch):
    """Force the direct-LLM path on and stub the Anthropic call.

    Set state['reply'] to a JSON string to simulate success, or to an
    LLMError instance to simulate a failure. state['prompts'] records every
    prompt sent (for asserting the exclude clause on re-roll)."""
    from app import llm_client
    state = {"reply": "", "prompts": []}

    def _complete(prompt):
        state["prompts"].append(prompt)
        if isinstance(state["reply"], Exception):
            raise state["reply"]
        return state["reply"]

    monkeypatch.setattr(llm_client, "is_configured", lambda: True)
    monkeypatch.setattr(llm_client, "complete", _complete)
    return state
