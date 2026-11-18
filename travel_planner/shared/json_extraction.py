"""Robust extraction of a JSON object from free-form LLM output.

Language models frequently wrap JSON in prose or Markdown code fences, so the
first ``{`` / last ``}`` slicing used in the original prototype was fragile
(it crashed with ``ValueError`` when no brace was present). This helper scans
for the first position where a *valid* JSON object can be decoded.
"""

import json
from typing import Any

from travel_planner.shared.exceptions import LLMResponseFormatError

_DECODER = json.JSONDecoder()


def extract_json_object(text: str) -> dict[str, Any]:
    """Return the first JSON object embedded in ``text``.

    Raises:
        LLMResponseFormatError: if ``text`` is not a string or contains no JSON object.
    """
    if not isinstance(text, str):
        raise LLMResponseFormatError("LLM response is not text", raw_response=str(text))

    position = text.find("{")
    while position != -1:
        try:
            value, _ = _DECODER.raw_decode(text, position)
        except json.JSONDecodeError:
            position = text.find("{", position + 1)
            continue
        if isinstance(value, dict):
            return value
        position = text.find("{", position + 1)

    raise LLMResponseFormatError("No JSON object found in LLM response", raw_response=text)
