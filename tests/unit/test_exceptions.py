from travel_planner.shared.exceptions import (
    ExternalServiceError,
    InvalidRequestError,
    PersistenceError,
    TravelPlannerError,
)


def test_external_errors_are_retryable_by_default():
    error = ExternalServiceError("groq", "503 service unavailable")
    assert error.retryable is True
    assert error.retry_after_seconds is None
    assert error.service == "groq"


def test_external_error_can_be_marked_permanent_with_a_wait_time():
    error = ExternalServiceError("groq", "too large", retryable=False, retry_after_seconds=2.5)
    assert error.retryable is False
    assert error.retry_after_seconds == 2.5


def test_user_message_of_an_external_error_hides_technical_details():
    error = ExternalServiceError("groq", "Error code: 413 - organization org_123, tokens per minute 8000")
    assert "org_123" not in error.user_message
    assert "413" not in error.user_message
    assert "groq" in error.user_message
    assert "try again" in error.user_message.lower()


def test_subclasses_of_external_errors_also_hide_details():
    assert "password" not in PersistenceError("database", "connection failed: password=hunter2").user_message


def test_validation_messages_are_already_meant_for_the_user():
    assert InvalidRequestError("The request must be at least 10 characters long.").user_message == (
        "The request must be at least 10 characters long."
    )
    assert TravelPlannerError("plain").user_message == "plain"
