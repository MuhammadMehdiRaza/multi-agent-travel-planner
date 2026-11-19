"""Decorator pattern: add logging and retries to ANY LLMClient without changing it.

This is the same structure as the LoggingNotifier example from the lectures:

    LLMClient (interface)
      +-- GroqChatAdapter          the real work
      +-- LLMClientDecorator       IS an LLMClient and HAS an LLMClient
            +-- LoggingLLMClient   adds timing/logging
            +-- RetryingLLMClient  adds retry with back-off

Usage:  RetryingLLMClient(LoggingLLMClient(GroqChatAdapter(...)))
"""

import logging
import time

from travel_planner.llm.ports import LLMClient
from travel_planner.shared.exceptions import ExternalServiceError

logger = logging.getLogger("travel_planner.llm")


# Design pattern: Decorator (structural) - IS an LLMClient and HAS an LLMClient, so decorators stack.
# SOLID - OCP: new LLM behaviour (caching, metrics, ...) is a new decorator; no existing class changes.
# SOLID - LSP: a decorated client can replace the plain client anywhere an LLMClient is expected.
class LLMClientDecorator(LLMClient):
    """Base decorator: forwards every call to the wrapped client."""

    def __init__(self, wrapped: LLMClient):
        self._wrapped = wrapped

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return self._wrapped.complete(system_prompt, user_prompt)


# SOLID - SRP: this decorator only logs; retrying is a separate decorator.
class LoggingLLMClient(LLMClientDecorator):
    """Logs how long each LLM call takes (replaces the print() blocks of the prototype)."""

    def __init__(self, wrapped: LLMClient, label: str = "llm"):
        super().__init__(wrapped)
        self._label = label

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        start = time.perf_counter()
        try:
            answer = super().complete(system_prompt, user_prompt)
        except ExternalServiceError as error:
            logger.warning("[%s] LLM call failed after %.2fs: %s", self._label, time.perf_counter() - start, error)
            raise
        logger.debug(
            "[%s] LLM call took %.2fs (prompt %d chars, answer %d chars)",
            self._label, time.perf_counter() - start, len(user_prompt), len(answer),
        )
        return answer


class RetryingLLMClient(LLMClientDecorator):
    """Retries temporary service failures (e.g. HTTP 503 / rate limit) with exponential back-off.

    NOT retried: format errors (asking again rarely fixes them) and permanent service errors
    such as "request too large" or "unknown model" (sending the same request again cannot work).
    When the service says how long to wait (rate limit), that wait is used, up to MAX_WAIT_SECONDS.
    """

    MAX_WAIT_SECONDS = 30

    def __init__(self, wrapped: LLMClient, max_attempts: int = 3, backoff_seconds: float = 1.0, sleep=time.sleep):
        super().__init__(wrapped)
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds
        self._sleep = sleep  # injectable so tests do not really wait

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        delay = self._backoff_seconds
        for attempt in range(1, self._max_attempts + 1):
            try:
                return super().complete(system_prompt, user_prompt)
            except ExternalServiceError as error:
                if not error.retryable or attempt == self._max_attempts:
                    raise
                wait = min(max(delay, error.retry_after_seconds or 0), self.MAX_WAIT_SECONDS)
                logger.info("Retrying LLM call in %.1fs (attempt %d of %d)", wait, attempt + 1, self._max_attempts)
                self._sleep(wait)
                delay = delay * 2
        raise AssertionError("unreachable")  # the loop always returns or raises
