import pytest

from travel_planner.intake.guardrail import LLMInputGuardrail
from travel_planner.shared.exceptions import ExternalServiceError
from tests.fakes import ScriptedLLMClient


def test_allowed_request_passes():
    guardrail = LLMInputGuardrail(ScriptedLLMClient(['{"allowed": true, "reason": ""}']))
    verdict = guardrail.check("Plan a trip to Japan")
    assert verdict.allowed


def test_blocked_request_returns_reason():
    llm = ScriptedLLMClient(['{"allowed": false, "reason": "Not a travel request."}'])
    verdict = LLMInputGuardrail(llm).check("Write my homework essay")
    assert not verdict.allowed
    assert verdict.reason == "Not a travel request."


def test_query_is_sent_to_the_model():
    llm = ScriptedLLMClient(['{"allowed": true}'])
    LLMInputGuardrail(llm).check("Weekend in Hunza")
    assert "Weekend in Hunza" in llm.prompts[0][1]


def test_malformed_model_output_fails_closed():
    verdict = LLMInputGuardrail(ScriptedLLMClient(["I think it is fine"])).check("Trip to Rome")
    assert not verdict.allowed
    assert "rephrase" in verdict.reason.lower()


@pytest.mark.parametrize("value", ['"true"', "1", "null"])
def test_only_a_real_boolean_true_allows_the_request(value):
    verdict = LLMInputGuardrail(ScriptedLLMClient([f'{{"allowed": {value}}}'])).check("Trip to Rome")
    assert not verdict.allowed


def test_blocked_request_without_reason_gets_default_reason():
    verdict = LLMInputGuardrail(ScriptedLLMClient(['{"allowed": false}'])).check("Tell me a joke")
    assert verdict.reason


def test_service_failure_is_propagated():
    class DownLLM(ScriptedLLMClient):
        def complete(self, system_prompt, user_prompt):
            raise ExternalServiceError("groq", "down")

    with pytest.raises(ExternalServiceError):
        LLMInputGuardrail(DownLLM()).check("Trip to Rome")
