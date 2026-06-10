import pytest
from app import llm_client


def test_is_configured_reflects_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm_client.is_configured() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert llm_client.is_configured() is True


def test_get_model_default_and_override(monkeypatch):
    monkeypatch.delenv("CHEFAI_LLM_MODEL", raising=False)
    assert llm_client.get_model() == "claude-sonnet-4-6"
    monkeypatch.setenv("CHEFAI_LLM_MODEL", "claude-haiku-4-5")
    assert llm_client.get_model() == "claude-haiku-4-5"


def test_complete_without_key_raises_llm_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm_client.LLMError):
        llm_client.complete("bonjour")


class _FakeBlock:
    type = "text"
    text = "réponse"


class _FakeMessage:
    content = [_FakeBlock()]


class _FakeStream:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return _FakeMessage()


class _FakeMessages:
    def stream(self, **kwargs):
        return _FakeStream()


class _FakeClient:
    """Records the options the SDK client was configured with (e.g. timeout)."""

    def __init__(self):
        self.messages = _FakeMessages()
        self.options = {}

    def with_options(self, **kwargs):
        self.options.update(kwargs)
        return self


def test_complete_returns_text(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(llm_client, "_client", lambda: _FakeClient())
    assert llm_client.complete("salut") == "réponse"


def test_complete_applies_wall_clock_timeout(monkeypatch):
    """A timeout must be set so a stalled stream degrades instead of hanging forever."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setenv("CHEFAI_LLM_TIMEOUT", "5")
    fake = _FakeClient()
    monkeypatch.setattr(llm_client, "_client", lambda: fake)
    llm_client.complete("salut")
    assert fake.options.get("timeout") == 5.0


class _BoomMessages:
    def stream(self, **kwargs):
        raise RuntimeError("network down")


class _BoomClient:
    def __init__(self):
        self.messages = _BoomMessages()

    def with_options(self, **kwargs):
        return self


def test_complete_wraps_sdk_failure_as_llm_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.setattr(llm_client, "_client", lambda: _BoomClient())
    with pytest.raises(llm_client.LLMError):
        llm_client.complete("salut")
