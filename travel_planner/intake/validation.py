"""Deterministic input validation - the first, cheapest line of defence.

These checks run BEFORE any LLM call, so empty, oversized or obviously
malicious requests cost nothing and never reach the model.
"""

import re

from travel_planner.shared.exceptions import InvalidRequestError

MIN_QUERY_LENGTH = 10
MAX_QUERY_LENGTH = 2000

# Common prompt-injection phrases. The LLM guardrail is the second line of defence.
BLOCKED_PATTERNS = [
    r"ignore (all |any )?(the )?(previous|prior|above) (instructions|rules)",
    r"disregard (all |any )?(the )?(previous|prior|above)",
    r"system prompt",
    r"you are now",
    r"<\s*script",
]


# SOLID - SRP: only checks length and prompt-injection phrases (no LLM, no routing).
class RequestValidator:
    """Validates and normalises a raw travel request typed by the user."""

    def validate(self, raw_query: str) -> str:
        """Return the cleaned request text, or raise InvalidRequestError explaining the problem."""
        if not isinstance(raw_query, str):
            raise InvalidRequestError("The travel request must be text.")

        query = self.normalise(raw_query)

        if not query:
            raise InvalidRequestError("Please enter a travel request.")
        if len(query) < MIN_QUERY_LENGTH:
            raise InvalidRequestError(f"The request must be at least {MIN_QUERY_LENGTH} characters long.")
        if len(query) > MAX_QUERY_LENGTH:
            raise InvalidRequestError(f"The request must be at most {MAX_QUERY_LENGTH} characters long.")

        for pattern in BLOCKED_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                raise InvalidRequestError("The request contains instructions that are not allowed.")

        return query

    @staticmethod
    def normalise(text: str) -> str:
        """Remove control characters and collapse all whitespace to single spaces."""
        kept = []
        for char in text:
            if char.isprintable() or char.isspace():  # drop invisible control characters
                kept.append(char)
        words = "".join(kept).split()  # split() also removes tabs, newlines and repeated spaces
        return " ".join(words)
