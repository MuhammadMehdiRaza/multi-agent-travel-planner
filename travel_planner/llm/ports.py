"""The LLM interface that every agent depends on (Dependency Inversion Principle).

Agents only know "something that can complete a prompt". They never import
Groq or LangChain directly, so the model provider can be changed - or replaced
by a fake in unit tests - without editing any agent.
"""

from abc import ABC, abstractmethod


# SOLID - DIP: every agent depends on this abstraction, not on a concrete model provider.
class LLMClient(ABC):
    """Interface for all language-model access."""

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Return the model's answer to a system prompt + user prompt.

        Raises:
            ExternalServiceError: if the model provider fails or cannot be reached.
        """
