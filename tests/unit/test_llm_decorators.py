import logging

import pytest

from travel_planner.llm.decorators import LoggingLLMClient, RetryingLLMClient
from travel_planner.llm.ports import LLMClient
from travel_planner.shared.exceptions import ExternalServiceError, LLMResponseFormatError
from tests.fakes import ScriptedLLMClient


class FlakyLLMClient(LLMClient):
    """Fails with a transient service error ``failures`` times, then succeeds."""

    def __init__(self, failures: int, error: Exception | None = None) -> None:
        self.failures = failures
        self.calls = 0
        self.error = error or ExternalServiceError("groq", "503 service unavailable")

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return "ok"


def test_retrying_client_recovers_from_transient_failures():
    sleeps = []
    inner = FlakyLLMClient(failures=2)
    client = RetryingLLMClient(inner, max_attempts=3, backoff_seconds=0.5, sleep=sleeps.append)

    assert client.complete("sys", "prompt") == "ok"
    assert inner.calls == 3
    assert sleeps == [0.5, 1.0]  # exponential back-off


def test_retrying_client_gives_up_after_max_attempts():
    inner = FlakyLLMClient(failures=5)
    client = RetryingLLMClient(inner, max_attempts=3, backoff_seconds=0, sleep=lambda _: None)

    with pytest.raises(ExternalServiceError):
        client.complete("sys", "prompt")
    assert inner.calls == 3


def test_retrying_client_does_not_retry_format_errors():
    inner = FlakyLLMClient(failures=1, error=LLMResponseFormatError("bad json"))
    client = RetryingLLMClient(inner, max_attempts=3, backoff_seconds=0, sleep=lambda _: None)

    with pytest.raises(LLMResponseFormatError):
        client.complete("sys", "prompt")
    assert inner.calls == 1


def test_retrying_client_rejects_invalid_configuration():
    with pytest.raises(ValueError):
        RetryingLLMClient(ScriptedLLMClient(["x"]), max_attempts=0)


def test_logging_client_delegates_and_logs(caplog):
    inner = ScriptedLLMClient(["final answer"])
    client = LoggingLLMClient(inner, label="itinerary")

    with caplog.at_level(logging.DEBUG, logger="travel_planner.llm"):
        assert client.complete("system", "user prompt") == "final answer"

    assert inner.prompts == [("system", "user prompt")]
    assert any("itinerary" in record.getMessage() for record in caplog.records)


def test_logging_client_logs_and_reraises_failures(caplog):
    client = LoggingLLMClient(FlakyLLMClient(failures=1), label="guardrail")

    with caplog.at_level(logging.WARNING, logger="travel_planner.llm"):
        with pytest.raises(ExternalServiceError):
            client.complete("s", "p")
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_decorators_are_stackable():
    inner = FlakyLLMClient(failures=1)
    client = RetryingLLMClient(LoggingLLMClient(inner, label="x"), backoff_seconds=0, sleep=lambda _: None)
    assert client.complete("s", "p") == "ok"


def test_retrying_client_does_not_retry_permanent_service_errors():
    inner = FlakyLLMClient(failures=5, error=ExternalServiceError("groq", "413 request too large", retryable=False))
    client = RetryingLLMClient(inner, max_attempts=3, backoff_seconds=0, sleep=lambda _: None)
    with pytest.raises(ExternalServiceError):
        client.complete("s", "u")
    assert inner.calls == 1


def test_retrying_client_waits_as_long_as_the_service_asks():
    sleeps = []
    inner = FlakyLLMClient(failures=1, error=ExternalServiceError("groq", "429 rate limit", retry_after_seconds=7))
    client = RetryingLLMClient(inner, max_attempts=3, backoff_seconds=0.5, sleep=sleeps.append)
    assert client.complete("s", "u") == "ok"
    assert sleeps == [7]


def test_retry_wait_is_capped():
    sleeps = []
    inner = FlakyLLMClient(failures=1, error=ExternalServiceError("groq", "429 rate limit", retry_after_seconds=300))
    client = RetryingLLMClient(inner, max_attempts=3, backoff_seconds=0.5, sleep=sleeps.append)
    client.complete("s", "u")
    assert sleeps == [RetryingLLMClient.MAX_WAIT_SECONDS]
