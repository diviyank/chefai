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


def is_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def get_model() -> str:
    return os.environ.get("CHEFAI_LLM_MODEL", DEFAULT_MODEL)


def get_timeout() -> float:
    return float(os.environ.get("CHEFAI_LLM_TIMEOUT", DEFAULT_TIMEOUT_S))


def _client():
    from anthropic import Anthropic
    return Anthropic()


_DEFAULT = object()


def complete(prompt: str, *, model: str = None, max_tokens: int = None,
             thinking=_DEFAULT, effort: str = None, system=None) -> str:
    """Send one user message, return the concatenated text reply. Raises LLMError.

    Keyword overrides let callers tune per-kind cost/latency. thinking defaults to
    adaptive; pass thinking=None to omit it (e.g. Haiku). effort/system are sent only
    when provided."""
    if not is_configured():
        raise LLMError("ANTHROPIC_API_KEY non configurée")
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
        raise LLMError(str(exc)) from exc
    return "".join(
        block.text for block in message.content
        if getattr(block, "type", None) == "text"
    )
