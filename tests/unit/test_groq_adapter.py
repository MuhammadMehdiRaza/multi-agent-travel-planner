from types import SimpleNamespace

import langchain_groq
import pytest

from travel_planner.llm.groq_adapter import MAX_ANSWER_TOKENS, GroqChatAdapter
from travel_planner.shared.exceptions import ConfigurationError, ExternalServiceError


class FakeChatGroq:
    """Stands in for the Groq SDK: records how it was created and what it was sent."""

    created = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.messages = None
        self.error = None
        FakeChatGroq.created.append(self)

    def invoke(self, messages):
        self.messages = messages
        if self.error:
            raise self.error
        return SimpleNamespace(content="answer")


class StatusError(Exception):
    """Shaped like the Groq SDK's APIStatusError (status_code + response headers)."""

    def __init__(self, status_code, headers=None):
        super().__init__(f"Error code: {status_code} - org_123 secret details")
        self.status_code = status_code
        self.response = SimpleNamespace(headers=headers or {})


@pytest.fixture(name="fake_groq")
def fake_groq_fixture(monkeypatch):
    FakeChatGroq.created.clear()
    monkeypatch.setattr(langchain_groq, "ChatGroq", FakeChatGroq)
    return FakeChatGroq


def test_missing_key_is_a_configuration_error(fake_groq):
    with pytest.raises(ConfigurationError, match="GROQ_API_KEY"):
        GroqChatAdapter("openai/gpt-oss-120b", "")
    assert fake_groq.created == []


def test_answer_length_is_capped_so_requests_fit_the_free_tier(fake_groq):
    GroqChatAdapter("openai/gpt-oss-120b", "key")
    assert fake_groq.created[0].kwargs["max_tokens"] == MAX_ANSWER_TOKENS


def test_gpt_oss_models_use_low_reasoning_effort(fake_groq):
    GroqChatAdapter("openai/gpt-oss-120b", "key")
    assert fake_groq.created[0].kwargs["reasoning_effort"] == "low"


def test_other_models_are_not_sent_a_reasoning_setting(fake_groq):
    GroqChatAdapter("qwen/qwen3.8-27b", "key")
    assert "reasoning_effort" not in fake_groq.created[0].kwargs


def test_complete_sends_system_and_user_messages_and_returns_text(fake_groq):
    adapter = GroqChatAdapter("openai/gpt-oss-120b", "key")
    assert adapter.complete("be brief", "plan a trip") == "answer"
    sent = fake_groq.created[0].messages
    assert [message.content for message in sent] == ["be brief", "plan a trip"]


@pytest.mark.parametrize("status", [400, 401, 404, 413])
def test_permanent_errors_are_not_retryable(fake_groq, status):
    adapter = GroqChatAdapter("openai/gpt-oss-120b", "key")
    fake_groq.created[0].error = StatusError(status)
    with pytest.raises(ExternalServiceError) as caught:
        adapter.complete("s", "u")
    assert caught.value.retryable is False


def test_rate_limit_is_retryable_after_the_wait_the_service_asks_for(fake_groq):
    adapter = GroqChatAdapter("openai/gpt-oss-120b", "key")
    fake_groq.created[0].error = StatusError(429, {"retry-after": "3"})
    with pytest.raises(ExternalServiceError) as caught:
        adapter.complete("s", "u")
    assert caught.value.retryable is True
    assert caught.value.retry_after_seconds == 3.0


@pytest.mark.parametrize("error", [StatusError(503), ConnectionError("network down")])
def test_server_and_network_errors_are_retryable(fake_groq, error):
    adapter = GroqChatAdapter("openai/gpt-oss-120b", "key")
    fake_groq.created[0].error = error
    with pytest.raises(ExternalServiceError) as caught:
        adapter.complete("s", "u")
    assert caught.value.retryable is True
    assert caught.value.retry_after_seconds is None
