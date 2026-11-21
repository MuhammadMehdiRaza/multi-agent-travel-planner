"""End-to-end tests of the LangGraph workflow through the facade.

Real graph, real routing/budget/persistence code and the real sample-data
integration family - only the LLM is replaced by a scripted fake.
"""

import json

import pytest

from travel_planner.bootstrap import assemble_facade
from travel_planner.factories import SampleIntegrationFactory
from travel_planner.settings import Settings
from travel_planner.shared.exceptions import ExternalServiceError, InvalidApprovalError, PersistenceError
from travel_planner.workflow.facade import PlanStatus
from travel_planner.workflow.plan_store import SqlitePlanStore
from tests.fakes import RoutingLLMClient

JAPAN_QUERY = "Plan a complete 7 days Japan trip including flights, hotels and sightseeing under 2 lakhs"

ROUTING_JSON = json.dumps({
    "selected_agents": ["flight_agent", "hotel_agent", "weather_agent", "budget_agent", "itinerary_agent"],
    "trip_constraints": {"destination": "Japan", "duration": "7 days", "budget": "2 lakhs", "travel_style": "budget"},
    "reasoning": "Full trip with a budget.",
})


def guardrail(prompt):
    if "homework" in prompt:
        return '{"allowed": false, "reason": "Only travel requests are supported."}'
    return '{"allowed": true, "reason": ""}'


def itinerary(prompt):
    return "Draft v2 with Kyoto" if "Reviewer feedback" in prompt else "Draft v1"


def make_llm(**overrides):
    rules = {
        "guardrail": guardrail,
        "route work": ROUTING_JSON,
        "flight planning": "Flight guidance: PIA to Narita",
        "hotel and accommodation": "Hotel guidance: Shinjuku",
        "budget analyst": "Travel in the off-season.",
        "itinerary planner": itinerary,
        "final, user-ready": "FINAL PLAN",
    }
    rules.update(overrides)
    return RoutingLLMClient(rules)


def make_settings(tmp_path, **env):
    values = {"GROQ_API_KEY": "test", "SQLITE_PATH": str(tmp_path / "plans.sqlite3")}
    values.update(env)
    return Settings.from_env(values)


def make_facade(tmp_path, llm=None, factory=None, **env):
    settings = make_settings(tmp_path, **env)
    return assemble_facade(settings, llm or make_llm(), factory or SampleIntegrationFactory(settings))


# ------------------------------------------------------------------ happy paths
def test_request_runs_all_agents_and_waits_for_approval(tmp_path):
    snapshot = make_facade(tmp_path).start_planning("mehdi", JAPAN_QUERY)

    assert snapshot.status is PlanStatus.AWAITING_APPROVAL
    assert snapshot.selected_agents == (
        "flight_agent", "hotel_agent", "weather_agent", "budget_agent", "itinerary_agent")
    assert snapshot.sections["Flights"] == "Flight guidance: PIA to Narita"
    assert "SAMPLE DATA" in snapshot.sections["Weather"]
    assert "OVER BUDGET" in snapshot.sections["Budget"]
    assert snapshot.budget_verdict == "OVER_BUDGET"
    assert snapshot.draft_itinerary == "Draft v1"
    assert snapshot.final_plan == ""


def test_approval_completes_and_stores_the_plan(tmp_path):
    facade = make_facade(tmp_path)
    started = facade.start_planning("mehdi", JAPAN_QUERY)

    done = facade.submit_decision(started.thread_id, approved=True, feedback="")

    assert done.status is PlanStatus.COMPLETED
    assert done.final_plan == "FINAL PLAN"
    history = facade.history("mehdi")
    assert len(history) == 1
    assert history[0].plan_id == done.plan_id
    assert history[0].destination == "Japan"
    assert history[0].approved is True


def test_rejection_with_feedback_produces_a_revised_draft(tmp_path):
    facade = make_facade(tmp_path)
    thread_id = facade.start_planning("mehdi", JAPAN_QUERY).thread_id

    revised = facade.submit_decision(thread_id, approved=False, feedback="Add a day in Kyoto")
    assert revised.status is PlanStatus.AWAITING_APPROVAL
    assert revised.draft_itinerary == "Draft v2 with Kyoto"
    assert revised.revision_count == 1

    done = facade.submit_decision(thread_id, approved=True, feedback="")
    assert done.status is PlanStatus.COMPLETED
    assert facade.history("mehdi")[0].revision_count == 1


def test_revision_limit_finalises_with_feedback(tmp_path):
    facade = make_facade(tmp_path, MAX_REVISIONS="1")
    thread_id = facade.start_planning("mehdi", JAPAN_QUERY).thread_id
    facade.submit_decision(thread_id, approved=False, feedback="cheaper")

    done = facade.submit_decision(thread_id, approved=False, feedback="still too expensive")

    assert done.status is PlanStatus.COMPLETED
    assert facade.history("mehdi")[0].approved is False


# ------------------------------------------------------------------ rejected requests
def test_guardrail_rejection_stops_before_research(tmp_path):
    llm = make_llm()
    snapshot = make_facade(tmp_path, llm=llm).start_planning("mehdi", "Please solve my calculus homework for me")

    assert snapshot.status is PlanStatus.REJECTED
    assert snapshot.rejection_reason == "Only travel requests are supported."
    assert not any("flight planning" in system.lower() for system, _ in llm.prompts)


def test_invalid_request_is_rejected_without_calling_the_llm(tmp_path):
    llm = make_llm()
    snapshot = make_facade(tmp_path, llm=llm).start_planning("mehdi", "hi")
    assert snapshot.status is PlanStatus.REJECTED
    assert llm.prompts == []


@pytest.mark.parametrize("user_id", ["", "   ", "x" * 101])
def test_invalid_user_id_is_rejected(tmp_path, user_id):
    with pytest.raises(Exception, match="User ID"):
        make_facade(tmp_path).start_planning(user_id, JAPAN_QUERY)


# ------------------------------------------------------------------ approval misuse
def test_rejection_without_feedback_is_refused_and_plan_keeps_waiting(tmp_path):
    facade = make_facade(tmp_path)
    thread_id = facade.start_planning("mehdi", JAPAN_QUERY).thread_id
    with pytest.raises(InvalidApprovalError):
        facade.submit_decision(thread_id, approved=False, feedback="")
    assert facade.snapshot(thread_id).status is PlanStatus.AWAITING_APPROVAL


def test_decision_for_a_finished_plan_is_refused(tmp_path):
    facade = make_facade(tmp_path)
    thread_id = facade.start_planning("mehdi", JAPAN_QUERY).thread_id
    facade.submit_decision(thread_id, approved=True, feedback="")
    with pytest.raises(InvalidApprovalError, match="not waiting"):
        facade.submit_decision(thread_id, approved=True, feedback="")


# ------------------------------------------------------------------ injected failures
def test_malformed_routing_output_falls_back_to_keyword_rules(tmp_path):
    snapshot = make_facade(tmp_path, llm=make_llm(**{"route work": "Sorry, I cannot do JSON"})).start_planning(
        "mehdi", JAPAN_QUERY)
    assert snapshot.status is PlanStatus.AWAITING_APPROVAL
    assert snapshot.routing_strategy == "keyword (fallback)"


def test_one_failing_research_agent_does_not_stop_the_plan(tmp_path):
    def flight_down(prompt):
        raise ExternalServiceError("groq", "rate limit")

    snapshot = make_facade(tmp_path, llm=make_llm(**{"flight planning": flight_down})).start_planning(
        "mehdi", JAPAN_QUERY)
    assert snapshot.status is PlanStatus.AWAITING_APPROVAL
    assert snapshot.research_failures == ("Flight",)
    assert "unavailable" in snapshot.sections["Flights"]
    assert snapshot.sections["Hotels"] == "Hotel guidance: Shinjuku"


def test_storage_failure_still_returns_the_final_plan(tmp_path):
    class BrokenStore(SqlitePlanStore):
        def save_plan(self, record):
            raise PersistenceError("sqlite", "disk full")

    class BrokenStoreFactory(SampleIntegrationFactory):
        def create_plan_store(self):
            return BrokenStore(self._settings.sqlite_path)

    settings = make_settings(tmp_path)
    facade = assemble_facade(settings, make_llm(), BrokenStoreFactory(settings))
    thread_id = facade.start_planning("mehdi", JAPAN_QUERY).thread_id
    done = facade.submit_decision(thread_id, approved=True, feedback="")

    assert done.status is PlanStatus.COMPLETED
    assert done.final_plan == "FINAL PLAN"
    assert "could not be saved" in done.storage_warning


def test_long_valid_user_id_does_not_exceed_the_thread_id_schema(tmp_path):
    facade = make_facade(tmp_path)
    user_id = "u" * 100  # the longest user ID the facade accepts
    draft = facade.start_planning(user_id, JAPAN_QUERY)
    assert len(draft.thread_id) <= 100  # thread_id is VARCHAR(100) in schema.sql
    done = facade.submit_decision(draft.thread_id, True, "")
    assert facade.history(user_id)[0].plan_id == done.plan_id
