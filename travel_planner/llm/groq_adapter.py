"""Adapter pattern: makes LangChain's ChatGroq fit our LLMClient interface.

    Target  = LLMClient.complete(system_prompt, user_prompt) -> str   (what our agents want)
    Adaptee = ChatGroq.invoke([SystemMessage, HumanMessage]) -> AIMessage   (what the SDK offers)
    Adapter = GroqChatAdapter   (translates between the two)
"""

from langchain_core.messages import HumanMessage, SystemMessage

from travel_planner.llm.ports import LLMClient
from travel_planner.shared.exceptions import ConfigurationError, ExternalServiceError

# Groq's free tier allows 8,000 tokens per minute and counts the requested answer length,
# so every request asks for at most this many answer tokens.
MAX_ANSWER_TOKENS = 2048


def is_permanent_error(status_code) -> bool:
    """HTTP 400-428 (bad request, unknown model, request too large) fail again if the same request is sent."""
    if status_code is None:  # no HTTP status, e.g. a network error: worth trying again
        return False
    return 400 <= status_code <= 428


def retry_after_seconds(error: Exception) -> float | None:
    """Read the 'retry-after' header that Groq sends with a rate-limit (429) answer."""
    response = getattr(error, "response", None)  # not every error has an HTTP response
    if response is None:
        return None
    headers = getattr(response, "headers", None) or {}
    try:
        return float(headers.get("retry-after"))
    except (TypeError, ValueError):  # header missing or not a number
        return None


# Design pattern: Adapter (structural) - GroqChatAdapter is the adapter, ChatGroq the adaptee.
# SOLID - DIP: agents depend on the LLMClient abstraction, never on the Groq SDK.
class GroqChatAdapter(LLMClient):
    def __init__(self, model: str, api_key: str, temperature: float = 0.0):
        if not api_key:
            raise ConfigurationError("GROQ_API_KEY is not set, so the LLM cannot be created")

        # Imported here, not at the top of the file: importing this module stays light, and tests can
        # replace langchain_groq.ChatGroq with a fake (monkeypatch) before the adapter is created.
        from langchain_groq import ChatGroq  # pylint: disable=import-outside-toplevel

        options = {
            "model": model,
            "api_key": api_key,
            "temperature": temperature,
            "max_tokens": MAX_ANSWER_TOKENS,
            "timeout": 30.0,  # seconds; a hung request now fails instead of waiting forever
            "max_retries": 0,  # RetryingLLMClient is the only retry policy (no hidden SDK retries)
        }
        if model.startswith("openai/gpt-oss"):
            # gpt-oss models "think" before answering; low effort keeps the answers fast and short.
            options["reasoning_effort"] = "low"
        self._chat_model = ChatGroq(**options)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        try:
            response = self._chat_model.invoke(messages)
        except Exception as error:  # the SDK can raise many types; convert them to one of ours
            status_code = getattr(error, "status_code", None)  # None if the error has no HTTP status
            raise ExternalServiceError(
                "groq",
                str(error),
                retryable=not is_permanent_error(status_code),
                retry_after_seconds=retry_after_seconds(error),
            ) from error
        return str(response.content)
