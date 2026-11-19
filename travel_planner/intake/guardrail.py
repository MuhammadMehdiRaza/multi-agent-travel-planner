"""LLM-based guardrail: decides whether a request is really about travel planning."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from travel_planner.llm.ports import LLMClient
from travel_planner.shared.exceptions import LLMResponseFormatError
from travel_planner.shared.json_extraction import extract_json_object

logger = logging.getLogger(__name__)

GUARDRAIL_SYSTEM_PROMPT = "You are an input validation guardrail for a travel planner. Return strict JSON only."

GUARDRAIL_PROMPT = """Determine whether the following request is a valid travel planning request.

Return only JSON in this format:
{{"allowed": true, "reason": ""}}

User request:
{query}
"""

DEFAULT_BLOCK_REASON = "This assistant can only help with travel planning requests."
UNVERIFIED_REASON = "The request could not be verified as a travel request. Please rephrase it."


@dataclass(frozen=True)
class GuardrailVerdict:
    allowed: bool
    reason: str = ""


# SOLID - DIP: IntakeService depends on this interface, not on the LLM-based implementation.
class InputGuardrail(ABC):
    """Interface for any check that can allow or block a request."""

    @abstractmethod
    def check(self, query: str) -> GuardrailVerdict:
        """Return whether the request may be processed."""


class LLMInputGuardrail(InputGuardrail):
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def check(self, query: str) -> GuardrailVerdict:
        answer = self._llm.complete(GUARDRAIL_SYSTEM_PROMPT, GUARDRAIL_PROMPT.format(query=query))
        try:
            data = extract_json_object(answer)
        except LLMResponseFormatError:
            # Fail closed: if we cannot read the guardrail's decision, we do not let the request through.
            logger.warning("Guardrail returned unreadable output; blocking the request")
            return GuardrailVerdict(allowed=False, reason=UNVERIFIED_REASON)

        # Only a real JSON boolean `true` counts - not "true", 1 or null.
        if data.get("allowed") is True:
            return GuardrailVerdict(allowed=True)
        reason = str(data.get("reason") or DEFAULT_BLOCK_REASON)
        return GuardrailVerdict(allowed=False, reason=reason)
