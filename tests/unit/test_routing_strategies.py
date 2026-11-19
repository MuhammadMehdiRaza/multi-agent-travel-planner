import json

import pytest

from travel_planner.domain.models import AgentName, TravelStyle
from travel_planner.intake.routing import FallbackRoutingStrategy, KeywordRoutingStrategy, LLMRoutingStrategy
from travel_planner.shared.exceptions import ExternalServiceError, LLMResponseFormatError
from tests.fakes import ScriptedLLMClient

A = AgentName


# ------------------------------------------------------------------ keyword strategy
keyword = KeywordRoutingStrategy()


def test_generic_trip_request_selects_all_research_agents():
    decision = keyword.route("Plan a complete 7 days Japan trip including flights, hotels and sightseeing under 2 lakhs")
    assert decision.selected_agents == (A.FLIGHT, A.HOTEL, A.WEATHER, A.BUDGET, A.ITINERARY)
    assert decision.strategy_name == "keyword"


def test_specific_request_selects_only_matching_agents():
    decision = keyword.route("What will the weather be like in Istanbul next week?")
    assert decision.selected_agents == (A.WEATHER, A.ITINERARY)


def test_hotel_and_flight_keywords():
    decision = keyword.route("Find me a flight and a hotel in Dubai")
    assert decision.selected_agents == (A.FLIGHT, A.HOTEL, A.ITINERARY)


@pytest.mark.parametrize(
    "query, destination",
    [
        ("Plan a complete 7 days Japan trip", "Japan"),
        ("I want to travel to New York in December", "New York"),
        ("Weekend visit to Hunza with family", "Hunza"),
        ("Family holiday in Turkey", "Turkey"),
        ("plan something nice", ""),
    ],
)
def test_destination_extraction(query, destination):
    assert keyword.route(query).constraints.destination == destination


def test_origin_duration_and_budget_extraction():
    constraints = keyword.route("Fly from Lahore to Bangkok for 5 days under Rs. 150,000").constraints
    assert constraints.origin == "Lahore"
    assert constraints.destination == "Bangkok"
    assert constraints.duration_days == 5
    assert constraints.budget_text == "Rs. 150,000"


@pytest.mark.parametrize(
    "query, budget_text",
    [
        ("Japan trip under 2 lakhs", "2 lakhs"),
        ("Paris with a budget of $1500", "$1500"),
        ("Rome trip within 1200 USD", "1200 USD"),
        ("Trip to Rome", ""),
    ],
)
def test_budget_text_extraction(query, budget_text):
    assert keyword.route(query).constraints.budget_text == budget_text


def test_budget_agent_selected_when_budget_mentioned():
    assert keyword.route("Hotel in Paris within 1200 USD").includes(A.BUDGET)
    assert not keyword.route("Hotel in Paris").includes(A.BUDGET)


@pytest.mark.parametrize(
    "query, style",
    [
        ("Backpacking trip to Thailand staying in hostels", TravelStyle.BUDGET),
        ("Luxury honeymoon in the Maldives", TravelStyle.LUXURY),
        ("Trip to Japan under a budget of 2 lakhs", TravelStyle.MID_RANGE),
    ],
)
def test_travel_style_detection(query, style):
    assert keyword.route(query).constraints.travel_style is style


# ------------------------------------------------------------------ LLM strategy
def llm_reply(agents, **constraints):
    return json.dumps({"selected_agents": agents, "trip_constraints": constraints, "reasoning": "because"})


def test_llm_strategy_builds_decision_from_model_json():
    llm = ScriptedLLMClient([llm_reply(["flight_agent", "budget_agent"], destination="Japan", duration="7 days")])
    decision = LLMRoutingStrategy(llm).route("Japan trip")
    assert decision.selected_agents == (A.FLIGHT, A.BUDGET, A.ITINERARY)
    assert decision.constraints.destination == "Japan"
    assert decision.constraints.duration_days == 7
    assert decision.reasoning == "because"
    assert decision.strategy_name == "llm"


def test_llm_strategy_ignores_unknown_agents():
    llm = ScriptedLLMClient([llm_reply(["taxi_agent", "hotel_agent"])])
    assert LLMRoutingStrategy(llm).route("x").selected_agents == (A.HOTEL, A.ITINERARY)


@pytest.mark.parametrize(
    "reply",
    ["not json", '{"trip_constraints": {}}', '{"selected_agents": "flight_agent"}'],
)
def test_llm_strategy_rejects_invalid_output(reply):
    with pytest.raises(LLMResponseFormatError):
        LLMRoutingStrategy(ScriptedLLMClient([reply])).route("Japan trip")


# ------------------------------------------------------------------ fallback strategy
class FailingStrategy(LLMRoutingStrategy):
    def __init__(self, error):
        super().__init__(ScriptedLLMClient())
        self.error = error

    def route(self, query):
        raise self.error


@pytest.mark.parametrize("error", [LLMResponseFormatError("bad"), ExternalServiceError("groq", "down")])
def test_fallback_strategy_uses_keyword_rules_when_llm_fails(error):
    strategy = FallbackRoutingStrategy(primary=FailingStrategy(error), fallback=KeywordRoutingStrategy())
    decision = strategy.route("Weather in Istanbul")
    assert decision.selected_agents == (A.WEATHER, A.ITINERARY)
    assert decision.strategy_name == "keyword (fallback)"


def test_fallback_strategy_prefers_primary_when_it_works():
    primary = LLMRoutingStrategy(ScriptedLLMClient([llm_reply(["hotel_agent"])]))
    decision = FallbackRoutingStrategy(primary, KeywordRoutingStrategy()).route("Weather in Istanbul")
    assert decision.selected_agents == (A.HOTEL, A.ITINERARY)
    assert decision.strategy_name == "llm"
