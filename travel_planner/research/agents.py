"""The three research agents. Each depends only on the provider role it needs."""

from abc import ABC, abstractmethod

from travel_planner.domain.models import AgentName, TripConstraints
from travel_planner.llm.ports import LLMClient
from travel_planner.research.airports import DEFAULT_ORIGIN_AIRPORT, find_airport_code
from travel_planner.research.ports import FlightDataProvider, HotelSearchProvider, WeatherProvider
from travel_planner.shared.exceptions import InvalidRequestError


# SOLID - ISP / DIP: each agent receives only the provider role it needs and the LLMClient
# abstraction, through its constructor.
class ResearchAgent(ABC):
    """Interface for an agent that gathers one kind of external information."""

    name: AgentName

    @abstractmethod
    def research(self, query: str, constraints: TripConstraints) -> str:
        """Return a Markdown summary of the research for this trip."""


def require_destination(constraints: TripConstraints, label: str) -> str:
    if not constraints.destination:
        raise InvalidRequestError(f"{label} research needs a destination")
    return constraints.destination


FLIGHT_SYSTEM_PROMPT = "You are a flight planning specialist."
FLIGHT_PROMPT = """Create flight guidance for this trip.

User request:
{query}

Origin: {origin} (airport {origin_airport})
Destination: {destination} (airport {destination_airport})

Today's departures from {origin_airport} (live schedule sample):
{departures}

Include likely departure/arrival airports, airlines that connect them (directly or through a hub),
estimated duration, fare range, peak-season warning and booking advice.
If the origin is not specified, assume the traveller departs from Pakistan (Lahore, Karachi or Islamabad).
Give fares in Pakistani rupees (PKR) with approximate US dollars. Never use Indian rupees.
Do not calculate a total cost for the whole trip; our budget engine does that."""


class FlightResearchAgent(ResearchAgent):
    name = AgentName.FLIGHT

    def __init__(self, flights: FlightDataProvider, llm: LLMClient):
        self._flights = flights
        self._llm = llm

    def research(self, query: str, constraints: TripConstraints) -> str:
        destination = require_destination(constraints, "Flight")
        origin_airport = find_airport_code(constraints.origin) or DEFAULT_ORIGIN_AIRPORT
        # One AviationStack call per plan: the free plan allows about 100 calls a month
        # and rejects calls made in quick succession.
        prompt = FLIGHT_PROMPT.format(
            query=query,
            origin=constraints.origin or "not specified",
            origin_airport=origin_airport,
            destination=destination,
            destination_airport=find_airport_code(destination) or "unknown",
            departures=self._flights.departures(origin_airport),
        )
        return self._llm.complete(FLIGHT_SYSTEM_PROMPT, prompt)


HOTEL_SYSTEM_PROMPT = "You are a hotel and accommodation specialist."
HOTEL_PROMPT = """Using these search results, recommend where to stay.

User request:
{query}

Travel style: {style}

Search results:
{results}

List 3-5 areas or hotels with an approximate nightly price and one reason for each.
Give prices in Pakistani rupees (PKR) with approximate US dollars. Never use Indian rupees.
Do not calculate a total cost for the whole trip; our budget engine does that."""


class HotelResearchAgent(ResearchAgent):
    name = AgentName.HOTEL

    def __init__(self, hotels: HotelSearchProvider, llm: LLMClient):
        self._hotels = hotels
        self._llm = llm

    def research(self, query: str, constraints: TripConstraints) -> str:
        destination = require_destination(constraints, "Hotel")
        style = constraints.travel_style.value.replace("_", "-")
        results = self._hotels.search_hotels(f"Best {style} hotels and areas to stay in {destination}")
        prompt = HOTEL_PROMPT.format(query=query, style=style, results=results)
        return self._llm.complete(HOTEL_SYSTEM_PROMPT, prompt)


class WeatherResearchAgent(ResearchAgent):
    """Weather data is already structured, so no LLM call is needed here."""

    name = AgentName.WEATHER

    def __init__(self, weather: WeatherProvider):
        self._weather = weather

    def research(self, query: str, constraints: TripConstraints) -> str:
        city = require_destination(constraints, "Weather")
        current = self._weather.current_conditions(city)
        forecast = self._weather.forecast(city)
        return f"**Current weather ({city}):**\n{current}\n\n**Forecast:**\n{forecast}"
