"""Adapter pattern: make the vendor MCP tools fit our provider interfaces.

    Target  = FlightDataProvider / HotelSearchProvider / WeatherProvider (our vocabulary)
    Adaptee = MCP tools "flight_arrival_departure_schedule", "tavily_search", "get_forecast", ...
              (vendor vocabulary)
    Adapter = McpFlightDataAdapter, McpHotelSearchAdapter, McpWeatherAdapter

Only these three classes know the vendor tool names and argument formats. If
AviationStack is replaced by another flight API, only McpFlightDataAdapter changes.
"""

import json

from travel_planner.research.mcp_gateway import ToolGateway
from travel_planner.research.ports import FlightDataProvider, HotelSearchProvider, WeatherProvider
from travel_planner.shared.exceptions import ExternalServiceError

MAX_RESULT_CHARS = 3000  # keeps LLM prompts small


def tool_result_to_text(result, max_chars: int = MAX_RESULT_CHARS) -> str:
    """MCP tools return strings, dicts or lists of content blocks; turn any of them into text."""
    if result is None:
        text = ""
    elif isinstance(result, str):
        text = result
    elif isinstance(result, list):
        parts = []
        for item in result:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        text = "\n".join(parts)
    else:
        text = str(result)

    if len(text) > max_chars:
        text = text[:max_chars] + " ...[truncated]"
    return text


# Design pattern: Adapter (structural) - translates FlightDataProvider calls into the AviationStack MCP tool.
# Only the flight schedule tool is used, because it is included in AviationStack's free plan
# (the airport and airline search tools need a paid plan).
class McpFlightDataAdapter(FlightDataProvider):
    def __init__(self, gateway: ToolGateway):
        self._gateway = gateway

    def departures(self, airport_code: str, limit: int = 10) -> str:
        result = self._gateway.call_tool(
            "flight_arrival_departure_schedule",
            {"airport_iata_code": airport_code, "schedule_type": "departure", "number_of_flights": limit},
        )
        text = tool_result_to_text(result)
        # AviationStack reports failures (quota used up, plan limit) as {"ok": false, "error": ...}
        # instead of raising, so the adapter turns that reply into our own exception.
        error = aviationstack_error(text)
        if error:
            raise ExternalServiceError("AviationStack", error)
        return text


def aviationstack_error(text: str) -> str:
    """Return the error message of an AviationStack error reply, or "" for normal data."""
    if not text.startswith("{"):
        return ""
    try:
        reply = json.loads(text)
    except ValueError:
        return ""
    if isinstance(reply, dict) and reply.get("ok") is False:
        return str(reply.get("error", "unknown error"))
    return ""


# Design pattern: Adapter (structural) - translates HotelSearchProvider calls into the Tavily MCP tool.
class McpHotelSearchAdapter(HotelSearchProvider):
    def __init__(self, gateway: ToolGateway):
        self._gateway = gateway

    def search_hotels(self, query: str) -> str:
        return tool_result_to_text(self._gateway.call_tool("tavily_search", {"query": query}))


# Design pattern: Adapter (structural) - translates WeatherProvider calls into our weather MCP tools.
class McpWeatherAdapter(WeatherProvider):
    def __init__(self, gateway: ToolGateway):
        self._gateway = gateway

    def current_conditions(self, city: str) -> str:
        return tool_result_to_text(self._gateway.call_tool("get_current_weather", {"city": city}))

    def forecast(self, city: str) -> str:
        return tool_result_to_text(self._gateway.call_tool("get_forecast", {"city": city}))
