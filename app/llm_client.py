"""The ONLY module that talks to the Anthropic API. Keeps prompt_builder /
response_parser pure: build a prompt -> complete() -> parse the reply text."""
import os

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8000
# Wall-clock guard (seconds). Streaming read timeouts are per-chunk, so a stalled
# stream would otherwise block the request forever and the browser would spin with
# no result. On timeout the SDK raises -> LLMError -> the route shows the copy-paste
# prompt fallback. Override with CHEFAI_LLM_TIMEOUT.
DEFAULT_TIMEOUT_S = 120.0


class LLMError(RuntimeError):
    """Any failure talking to Claude (missing key, network, API error, refusal)."""
    # User-facing notice shown when the direct path degrades to copy-paste.
    notice = "Génération directe indisponible — copiez le prompt ci-dessous."


class AuthError(LLMError):
    """Credentials rejected (401) or absent. Distinct from a transient failure so the
    UI can tell the user the key itself is wrong instead of a generic 'unavailable'."""
    notice = ("Clé API Claude refusée (401) — vérifiez ANTHROPIC_API_KEY "
              "(guillemets superflus ? clé invalide ?). Copiez le prompt ci-dessous.")


def get_api_key() -> str | None:
    """The API key, normalized. A key wrapped in quotes in .env (ANTHROPIC_API_KEY=
    "sk-ant-...") is a common footgun: it looks present but the surrounding quotes make
    the API reject it with 401 invalid x-api-key. Docker Compose strips such quotes but
    a raw shell/`env` export does not, so we normalize here. Anthropic keys never start
    with a quote, so stripping matched surrounding quotes/whitespace is safe."""
    raw = os.environ.get("ANTHROPIC_API_KEY")
    if raw is None:
        return None
    return raw.strip().strip("\"'").strip() or None


def is_configured() -> bool:
    return bool(get_api_key())


def get_model() -> str:
    return os.environ.get("CHEFAI_LLM_MODEL", DEFAULT_MODEL)


def get_timeout() -> float:
    return float(os.environ.get("CHEFAI_LLM_TIMEOUT", DEFAULT_TIMEOUT_S))


def _client():
    from anthropic import Anthropic
    return Anthropic(api_key=get_api_key())


_DEFAULT = object()


def complete(prompt: str, *, model: str = None, max_tokens: int = None,
             thinking=_DEFAULT, effort: str = None, system=None) -> str:
    """Send one user message, return the concatenated text reply. Raises LLMError.

    Keyword overrides let callers tune per-kind cost/latency. thinking defaults to
    adaptive; pass thinking=None to omit it (e.g. Haiku). effort/system are sent only
    when provided."""
    if not is_configured():
        raise AuthError("ANTHROPIC_API_KEY non configurée")
    kwargs = {
        "model": model or get_model(),
        "max_tokens": max_tokens or MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }
    resolved_thinking = {"type": "adaptive"} if thinking is _DEFAULT else thinking
    if resolved_thinking is not None:
        kwargs["thinking"] = resolved_thinking
    if effort is not None:
        kwargs["output_config"] = {"effort": effort}
    if system is not None:
        kwargs["system"] = system
    try:
        client = _client().with_options(timeout=get_timeout())
        with client.messages.stream(**kwargs) as stream:
            message = stream.get_final_message()
    except Exception as exc:  # SDK APIError, network, etc. -> uniform LLMError
        if getattr(exc, "status_code", None) == 401:
            raise AuthError(str(exc)) from exc
        raise LLMError(str(exc)) from exc
    return "".join(
        block.text for block in message.content
        if getattr(block, "type", None) == "text"
    )
