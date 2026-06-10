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


def complete(prompt: str) -> str:
    """Send one user message, return the concatenated text reply. Raises LLMError."""
    if not is_configured():
        raise LLMError("ANTHROPIC_API_KEY non configurée")
    try:
        client = _client().with_options(timeout=get_timeout())
        with client.messages.stream(
            model=get_model(),
            max_tokens=MAX_TOKENS,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            message = stream.get_final_message()
    except Exception as exc:  # SDK APIError, network, etc. -> uniform LLMError
        raise LLMError(str(exc)) from exc
    return "".join(
        block.text for block in message.content
        if getattr(block, "type", None) == "text"
    )
