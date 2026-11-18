"""Exception hierarchy shared by every module.

All errors raised deliberately by the application derive from
``TravelPlannerError`` so that module boundaries (graph nodes, the facade,
the Streamlit UI) can catch *application* failures specifically, without
resorting to bare ``except Exception`` handlers.
"""


class TravelPlannerError(Exception):
    """Base class for all errors raised deliberately by the application."""

    @property
    def user_message(self) -> str:
        """Text that is safe to show in the UI (subclasses hide technical details)."""
        return str(self)


class ConfigurationError(TravelPlannerError):
    """Required configuration (environment variable, path, key) is missing or invalid."""


class ValidationError(TravelPlannerError):
    """A value violates a domain invariant (negative money, empty feedback, ...)."""


class InvalidRequestError(ValidationError):
    """A user's travel request was rejected by deterministic input validation."""


class InvalidApprovalError(ValidationError):
    """A human approval decision is malformed or incomplete."""


class LLMResponseFormatError(TravelPlannerError):
    """The language model returned output that does not match the expected format."""

    def __init__(self, message: str, raw_response: str = "") -> None:
        super().__init__(message)
        self.raw_response = raw_response


class ExternalServiceError(TravelPlannerError):
    """An external dependency (LLM API, MCP server, database) failed.

    retryable           False for permanent failures (bad request, unknown model, request too large)
    retry_after_seconds how long the service asked us to wait before trying again, if it said so
    """

    def __init__(self, service: str, message: str, retryable: bool = True,
                 retry_after_seconds: float | None = None) -> None:
        super().__init__(f"{service}: {message}")
        self.service = service
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds

    @property
    def user_message(self) -> str:
        # The full message can contain status codes, account ids or URLs: it is logged, never shown.
        return f"The {self.service} service is not available right now. Please try again in a minute."


class ToolNotFoundError(ExternalServiceError):
    """The requested MCP tool is not exposed by any connected MCP server."""


class ResearchTimeoutError(ExternalServiceError):
    """An external call did not complete within its time budget."""


class PersistenceError(ExternalServiceError):
    """Reading from or writing to the plan store failed."""
