import pytest
from app import llm_client


def test_is_configured_reflects_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm_client.is_configured() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert llm_client.is_configured() is True


def test_get_api_key_strips_surrounding_quotes(monkeypatch):
    """A key quoted in .env (ANTHROPIC_API_KEY="sk-...") 401s as-is; normalize it."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", '"sk-ant-quoted"')
    assert llm_client.get_api_key() == "sk-ant-quoted"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "'sk-ant-single'")
    assert llm_client.get_api_key() == "sk-ant-single"
    monkeypatch.setenv("ANTHROPIC_API_KEY", "  sk-ant-ws \n")
    assert llm_client.get_api_key() == "sk-ant-ws"


def test_get_api_key_none_when_unset_or_empty(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm_client.get_api_key() is None
    assert llm_client.is_configured() is False
    monkeypatch.setenv("ANTHROPIC_API_KEY", '""')   # empty after stripping quotes
    assert llm_client.get_api_key() is None
    assert llm_client.is_configured() is False


def test_get_model_default_and_override(monkeypatch):
    monkeypatch.delenv("CHEFAI_LLM_MODEL", raising=False)
    assert llm_client.get_model() == "claude-sonnet-4-6"
    monkeypatch.setenv("CHEFAI_LLM_MODEL", "claude-haiku-4-5")
    assert llm_client.get_model() == "claude-haiku-4-5"


def test_complete_without_key_raises_auth_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(llm_client.AuthError):
        llm_client.complete("bonjour")


def test_complete_maps_401_to_auth_error(monkeypatch):
    """A 401 from the SDK must surface as AuthError so the UI can say 'key rejected'."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    class _Boom401(Exception):
        status_code = 401

    class _Messages:
        def stream(self, **kw):
            raise _Boom401("Error code: 401 - invalid x-api-key")

    class _Client:
        def __init__(self):
            self.messages = _Messages()

        def with_options(self, **kw):
            return self

    monkeypatch.setattr(llm_client, "_client", lambda: _Client())
    with pytest.raises(llm_client.AuthError):
        llm_client.complete("salut")


def test_auth_error_notice_is_distinct():
    assert issubclass(llm_client.AuthError, llm_client.LLMError)
    assert llm_client.AuthError.notice != llm_client.LLMError.notice
    assert "401" in llm_client.AuthError.notice


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


class _CapturingMessages:
    def __init__(self):
        self.kwargs = None

    def stream(self, **kwargs):
        self.kwargs = kwargs
        return _FakeStream()


class _CapturingClient:
    def __init__(self):
        self.messages = _CapturingMessages()

    def with_options(self, **kwargs):
        return self


def test_complete_forwards_overrides(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    cap = _CapturingClient()
    monkeypatch.setattr(llm_client, "_client", lambda: cap)
    llm_client.complete("hi", model="claude-haiku-4-5", max_tokens=1500,
                        thinking=None, effort="low", system="ctx")
    k = cap.messages.kwargs
    assert k["model"] == "claude-haiku-4-5"
    assert k["max_tokens"] == 1500
    assert "thinking" not in k                      # thinking=None -> omitted
    assert k["output_config"] == {"effort": "low"}
    assert k["system"] == "ctx"


def test_complete_defaults_to_adaptive_thinking(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    cap = _CapturingClient()
    monkeypatch.setattr(llm_client, "_client", lambda: cap)
    llm_client.complete("hi")
    assert cap.messages.kwargs["thinking"] == {"type": "adaptive"}
    assert "output_config" not in cap.messages.kwargs
