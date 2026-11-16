"""Hand-written test doubles shared by the test suite.

Because every high-level class depends on an abstraction (DIP), these fakes
can replace the Groq LLM, the MCP servers and the database in tests that run
in milliseconds without network access.
"""

from typing import Callable, Iterable

from travel_planner.llm.ports import LLMClient


class ScriptedLLMClient(LLMClient):
    """LLMClient fake that returns pre-scripted responses and records prompts."""

    def __init__(self, responses: Iterable[str] | None = None, default: str | None = None) -> None:
        self._responses = list(responses or [])
        self._default = default
        self.prompts: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.prompts.append((system_prompt, user_prompt))
        if self._responses:
            return self._responses.pop(0)  # the oldest scripted answer first
        if self._default is not None:
            return self._default
        raise AssertionError("ScriptedLLMClient ran out of scripted responses")

    @property
    def call_count(self) -> int:
        return len(self.prompts)


class RoutingLLMClient(LLMClient):
    """LLMClient fake that chooses a response based on the system prompt."""

    def __init__(self, rules: dict[str, str | Callable[[str], str]], default: str = "generic response") -> None:
        self._rules = rules
        self._default = default
        self.prompts: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.prompts.append((system_prompt, user_prompt))
        for marker, response in self._rules.items():
            if marker.lower() in system_prompt.lower():
                if callable(response):  # a function decides the answer from the prompt
                    return response(user_prompt)
                return response
        return self._default
