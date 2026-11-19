from travel_planner.domain.models import AgentName
from travel_planner.intake.guardrail import GuardrailVerdict, InputGuardrail
from travel_planner.intake.routing import KeywordRoutingStrategy
from travel_planner.intake.service import IntakeService
from travel_planner.intake.validation import RequestValidator


class SpyGuardrail(InputGuardrail):
    def __init__(self, allowed=True, reason=""):
        self.verdict = GuardrailVerdict(allowed, reason)
        self.calls = 0

    def check(self, query):
        self.calls += 1
        return self.verdict


class SpyRouter(KeywordRoutingStrategy):
    def __init__(self):
        self.calls = 0

    def route(self, query):
        self.calls += 1
        return super().route(query)


def make_service(guardrail=None, router=None):
    return IntakeService(RequestValidator(), guardrail or SpyGuardrail(), router or SpyRouter())


def test_invalid_request_is_rejected_before_any_llm_call():
    guardrail, router = SpyGuardrail(), SpyRouter()
    outcome = make_service(guardrail, router).process("   ")
    assert not outcome.accepted
    assert outcome.rejection_reason
    assert guardrail.calls == 0
    assert router.calls == 0


def test_guardrail_rejection_stops_routing():
    router = SpyRouter()
    outcome = make_service(SpyGuardrail(allowed=False, reason="Not about travel."), router).process(
        "Solve my calculus homework please"
    )
    assert not outcome.accepted
    assert outcome.rejection_reason == "Not about travel."
    assert router.calls == 0


def test_accepted_request_returns_routing_decision():
    outcome = make_service().process("  Weather   in Istanbul next week ")
    assert outcome.accepted
    assert outcome.query == "Weather in Istanbul next week"
    assert outcome.decision.selected_agents == (AgentName.WEATHER, AgentName.ITINERARY)
