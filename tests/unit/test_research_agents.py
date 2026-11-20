import pytest

from travel_planner.domain.models import AgentName, TravelStyle, TripConstraints
from travel_planner.research.agents import FlightResearchAgent, HotelResearchAgent, WeatherResearchAgent
from travel_planner.research.mcp_adapters import (
    McpFlightDataAdapter,
    McpHotelSearchAdapter,
    McpWeatherAdapter,
    aviationstack_error,
    tool_result_to_text,
)
from travel_planner.research.mcp_gateway import ToolGateway
from travel_planner.research.sample_data import SampleFlightData, SampleHotelData, SampleWeatherData
from travel_planner.research.airports import DEFAULT_ORIGIN_AIRPORT, find_airport_code
from travel_planner.research.ports import FlightDataProvider
from travel_planner.shared.exceptions import ExternalServiceError, InvalidRequestError
from tests.fakes import ScriptedLLMClient

TOKYO = TripConstraints(destination="Tokyo", origin="Lahore", travel_style=TravelStyle.BUDGET)


class RecordingGateway(ToolGateway):
    def __init__(self, result="tool output"):
        self.calls = []
        self.result = result

    def call_tool(self, tool_name, arguments):
        self.calls.append((tool_name, arguments))
        return self.result


# ------------------------------------------------------------------ adapters (vendor tool -> our port)
def test_flight_adapter_uses_the_free_plan_schedule_tool():
    gateway = RecordingGateway()
    adapter = McpFlightDataAdapter(gateway)
    adapter.departures("LHE", limit=5)
    assert gateway.calls == [
        ("flight_arrival_departure_schedule",
         {"airport_iata_code": "LHE", "schedule_type": "departure", "number_of_flights": 5}),
    ]


def test_flight_adapter_turns_an_aviationstack_error_reply_into_an_exception():
    reply = '{"ok": false, "context": "fetching flight schedule", "error": "api_error (usage_limit_reached)"}'
    adapter = McpFlightDataAdapter(RecordingGateway(result=reply))
    with pytest.raises(ExternalServiceError, match="usage_limit_reached"):
        adapter.departures("LHE")


def test_flight_adapter_returns_normal_schedule_text():
    adapter = McpFlightDataAdapter(RecordingGateway(result='[{"airline": "Emirates", "arrival_airport_code": "DXB"}]'))
    assert "Emirates" in adapter.departures("LHE")


def test_hotel_and_weather_adapters_use_their_tools():
    gateway = RecordingGateway()
    McpHotelSearchAdapter(gateway).search_hotels("hotels in Tokyo")
    McpWeatherAdapter(gateway).current_conditions("Tokyo")
    McpWeatherAdapter(gateway).forecast("Tokyo")
    assert [name for name, _ in gateway.calls] == ["tavily_search", "get_current_weather", "get_forecast"]


@pytest.mark.parametrize(
    "result, expected",
    [
        ("plain", "plain"),
        ({"city": "Rome"}, "{'city': 'Rome'}"),
        ([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}], "a\nb"),
        (None, ""),
    ],
)
def test_tool_results_are_converted_to_text(result, expected):
    assert tool_result_to_text(result) == expected


def test_long_tool_results_are_truncated():
    assert len(tool_result_to_text("x" * 5000, max_chars=100)) <= 120


# ------------------------------------------------------------------ agents
def test_flight_agent_combines_provider_data_with_llm_summary():
    llm = ScriptedLLMClient(["Fly PIA to Narita"])
    agent = FlightResearchAgent(SampleFlightData(), llm)
    assert agent.name is AgentName.FLIGHT
    assert agent.research("Japan trip", TOKYO) == "Fly PIA to Narita"
    prompt = llm.prompts[0][1]
    assert "Tokyo" in prompt and "Lahore" in prompt


class RecordingFlightData(FlightDataProvider):
    def __init__(self):
        self.calls = []

    def departures(self, airport_code, limit=10):
        self.calls.append(airport_code)
        return f"departures from {airport_code}"


def test_flight_agent_makes_one_schedule_call_for_the_origin_airport():
    # The free plan allows about 100 calls a month and rejects calls made in quick succession.
    flights, llm = RecordingFlightData(), ScriptedLLMClient(["guide"])
    FlightResearchAgent(flights, llm).research("q", TOKYO)
    assert flights.calls == ["LHE"]
    prompt = llm.prompts[0][1]
    assert "departures from LHE" in prompt and "(airport NRT)" in prompt


def test_flight_agent_departs_from_lahore_when_no_origin_is_given():
    flights, llm = RecordingFlightData(), ScriptedLLMClient(["guide"])
    FlightResearchAgent(flights, llm).research("q", TripConstraints(destination="Dubai"))
    assert flights.calls == [DEFAULT_ORIGIN_AIRPORT]
    assert "(airport DXB)" in llm.prompts[0][1]


def test_flight_agent_still_works_when_the_destination_airport_is_unknown():
    flights, llm = RecordingFlightData(), ScriptedLLMClient(["guide"])
    FlightResearchAgent(flights, llm).research("q", TripConstraints(destination="Atlantis", origin="Karachi"))
    assert flights.calls == ["KHI"]
    assert "(airport unknown)" in llm.prompts[0][1]


# ------------------------------------------------------------------ airport codes
@pytest.mark.parametrize(
    "place, code",
    [
        ("Tokyo", "NRT"),
        ("Japan", "NRT"),
        ("Kyoto, Japan", "KIX"),
        ("lahore", "LHE"),
        ("New York", "JFK"),
        ("ISB", "ISB"),
        ("Atlantis", None),
        ("", None),
    ],
)
def test_find_airport_code(place, code):
    assert find_airport_code(place) == code


def test_hotel_agent_searches_for_the_travel_style():
    llm = ScriptedLLMClient(["Stay in Shinjuku"])
    assert HotelResearchAgent(SampleHotelData(), llm).research("q", TOKYO) == "Stay in Shinjuku"
    assert "budget" in llm.prompts[0][1].lower()


def test_weather_agent_needs_no_llm():
    text = WeatherResearchAgent(SampleWeatherData()).research("q", TOKYO)
    assert "Current weather" in text and "Forecast" in text and "Tokyo" in text


@pytest.mark.parametrize(
    "agent",
    [
        FlightResearchAgent(SampleFlightData(), ScriptedLLMClient()),
        HotelResearchAgent(SampleHotelData(), ScriptedLLMClient()),
        WeatherResearchAgent(SampleWeatherData()),
    ],
)
def test_agents_require_a_destination(agent):
    with pytest.raises(InvalidRequestError, match="destination"):
        agent.research("q", TripConstraints())


def test_flight_prompt_assumes_pakistan_and_pkr_when_no_origin_is_given():
    llm = ScriptedLLMClient(["guide"])
    FlightResearchAgent(SampleFlightData(), llm).research("q", TripConstraints(destination="Tokyo"))
    prompt = llm.prompts[0][1]
    assert "Pakistan" in prompt and "PKR" in prompt and "Never use Indian rupees" in prompt
    assert "Do not calculate a total cost for the whole trip" in prompt


def test_hotel_prompt_asks_for_pkr_prices():
    llm = ScriptedLLMClient(["hotels"])
    HotelResearchAgent(SampleHotelData(), llm).research("q", TOKYO)
    assert "PKR" in llm.prompts[0][1]
    assert "Do not calculate a total cost for the whole trip" in llm.prompts[0][1]


@pytest.mark.parametrize(
    "text, error",
    [
        ('{"ok": false, "error": "plan limit"}', "plan limit"),
        ('{"ok": false}', "unknown error"),
        ('{"city": "Tokyo"}', ""),
        ("{not json", ""),
        ('[{"airline": "PIA"}]', ""),
    ],
)
def test_aviationstack_error_replies_are_recognised(text, error):
    assert aviationstack_error(text) == error
