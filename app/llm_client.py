"""The ONLY module that talks to the Anthropic API. Keeps prompt_builder /
response_parser pure: build a prompt -> complete() -> parse the reply text."""
import os

DEFAULT_MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 8000


class LLMError(RuntimeError):
    """Any failure talking to Claude (missing key, network, API error, refusal)."""


def is_configured() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def get_model() -> str:
    return os.environ.get("CHEFAI_LLM_MODEL", DEFAULT_MODEL)


def _client():
    from anthropic import Anthropic
    return Anthropic()


def complete(prompt: str) -> str:
    """Send one user message, return the concatenated text reply. Raises LLMError."""
    if not is_configured():
        raise LLMError("ANTHROPIC_API_KEY non configurée")
    try:
        with _client().messages.stream(
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
