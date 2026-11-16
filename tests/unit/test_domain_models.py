import pytest

from travel_planner.domain.models import (
    AgentName,
    ResearchFinding,
    RoutingDecision,
    TravelStyle,
    TripConstraints,
    parse_duration_days,
)
from travel_planner.shared.exceptions import ValidationError


# ---------------------------------------------------------------- duration parsing
@pytest.mark.parametrize(
    "text, expected",
    [
        ("7 days", 7),
        ("7-day", 7),
        ("10 nights", 10),
        ("2 weeks", 14),
        ("a week", 7),
        ("one week", 7),
        ("weekend", 2),
        ("5", 5),
        (5, 5),
        ("", None),
        ("soon", None),
        (None, None),
    ],
)
def test_parse_duration_days(text, expected):
    assert parse_duration_days(text) == expected


# ---------------------------------------------------------------- travel style
@pytest.mark.parametrize(
    "text, expected",
    [
        ("budget backpacking", TravelStyle.BUDGET),
        ("cheap hostels", TravelStyle.BUDGET),
        ("luxury 5-star", TravelStyle.LUXURY),
        ("premium", TravelStyle.LUXURY),
        ("family", TravelStyle.MID_RANGE),
        ("", TravelStyle.MID_RANGE),
        (None, TravelStyle.MID_RANGE),
    ],
)
def test_travel_style_parse(text, expected):
    assert TravelStyle.parse(text) is expected


# ---------------------------------------------------------------- trip constraints
def test_constraints_from_llm_payload_normalises_types():
    payload = {
        "destination": "  Japan ",
        "origin": "Lahore",
        "duration": "7 days",
        "budget": "2 lakhs",
        "travel_style": "budget",
        "special_preferences": ["no overnight flights", "  ", "vegetarian food"],
    }
    constraints = TripConstraints.from_mapping(payload)
    assert constraints.destination == "Japan"
    assert constraints.duration_days == 7
    assert constraints.budget_text == "2 lakhs"
    assert constraints.travel_style is TravelStyle.BUDGET
    assert constraints.special_preferences == ("no overnight flights", "vegetarian food")


def test_constraints_from_mapping_tolerates_missing_and_wrong_types():
    constraints = TripConstraints.from_mapping({"destination": None, "special_preferences": "museums"})
    assert constraints.destination == ""
    assert constraints.duration_days is None
    assert constraints.special_preferences == ("museums",)


def test_constraints_round_trip_through_dict():
    original = TripConstraints(destination="Paris", duration_days=5, travel_style=TravelStyle.LUXURY)
    assert TripConstraints.from_mapping(original.to_dict()) == original


@pytest.mark.parametrize("days", [0, -1, 61])
def test_constraints_reject_out_of_range_duration(days):
    with pytest.raises(ValidationError):
        TripConstraints(destination="Paris", duration_days=days)


@pytest.mark.parametrize("days", [1, 60])
def test_constraints_accept_duration_boundaries(days):
    assert TripConstraints(duration_days=days).duration_days == days


def test_out_of_range_llm_duration_is_dropped_not_fatal():
    assert TripConstraints.from_mapping({"duration": "400 days"}).duration_days is None


def test_constraints_are_immutable():
    constraints = TripConstraints(destination="Rome")
    with pytest.raises(AttributeError):
        constraints.destination = "Milan"  # type: ignore[misc]


# ---------------------------------------------------------------- routing decision
def test_routing_decision_orders_dedupes_and_always_includes_itinerary():
    decision = RoutingDecision(
        selected_agents=(AgentName.BUDGET, AgentName.FLIGHT, AgentName.FLIGHT),
        constraints=TripConstraints(),
        reasoning="",
        strategy_name="test",
    )
    assert decision.selected_agents == (AgentName.FLIGHT, AgentName.BUDGET, AgentName.ITINERARY)


def test_routing_decision_exposes_research_agents_only():
    decision = RoutingDecision(
        selected_agents=(AgentName.WEATHER, AgentName.BUDGET, AgentName.HOTEL),
        constraints=TripConstraints(),
        reasoning="",
        strategy_name="test",
    )
    assert decision.research_agents == (AgentName.HOTEL, AgentName.WEATHER)
    assert decision.includes(AgentName.BUDGET)


def test_agent_name_parse_ignores_unknown_values():
    assert AgentName.parse_many(["flight_agent", "taxi_agent", "HOTEL_AGENT"]) == (
        AgentName.FLIGHT,
        AgentName.HOTEL,
    )


# ---------------------------------------------------------------- research finding
def test_failed_research_finding_has_no_summary():
    finding = ResearchFinding.failed(AgentName.WEATHER, "timeout", elapsed_seconds=1.5)
    assert not finding.succeeded
    assert finding.error == "timeout"
    assert "unavailable" in finding.display_text().lower()


def test_failed_research_text_hides_technical_details():
    finding = ResearchFinding.failed(
        AgentName.HOTEL, "HTTPStatusError: 401 for url https://mcp.tavily.com/mcp/?tavilyApiKey=tvly-secret", 0.2
    )
    text = finding.display_text()
    assert "unavailable" in text.lower()
    assert "tvly-secret" not in text and "401" not in text
    assert "tvly-secret" in finding.error  # the details are kept for the logs
