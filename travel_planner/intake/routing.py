"""Strategy pattern: interchangeable algorithms for choosing which agents to run.

    Context            = IntakeService (it only knows the RoutingStrategy interface)
    Strategy           = RoutingStrategy
    Concrete strategies:
        LLMRoutingStrategy       - asks the language model (smart, but can fail or return bad JSON)
        KeywordRoutingStrategy   - fixed keyword rules (simple, always works, works offline)
        FallbackRoutingStrategy  - tries one strategy and falls back to another on failure

The prototype hard-wired the LLM call inside one long supervisor function, so
a single malformed JSON answer crashed the whole request.
"""

import logging
import re
from abc import ABC, abstractmethod

from travel_planner.domain.models import (
    RESEARCH_AGENTS,
    AgentName,
    RoutingDecision,
    TravelStyle,
    TripConstraints,
    parse_duration_days,
)
from travel_planner.llm.ports import LLMClient
from travel_planner.shared.exceptions import ExternalServiceError, LLMResponseFormatError
from travel_planner.shared.json_extraction import extract_json_object

logger = logging.getLogger(__name__)


# Design pattern: Strategy (behavioural) - the routing algorithm is chosen at run time.
# SOLID - OCP: a new routing method is a new RoutingStrategy class; IntakeService is not edited.
# SOLID - LSP: every strategy returns a valid RoutingDecision, so they can replace each other.
class RoutingStrategy(ABC):
    name = "abstract"

    @abstractmethod
    def route(self, query: str) -> RoutingDecision:
        """Decide which agents to run for this (already validated) request."""


# --------------------------------------------------------------------------- LLM strategy
ROUTING_SYSTEM_PROMPT = "You route work to specialist travel agents. Return strict JSON only."

ROUTING_PROMPT = """You are the supervisor of a multi-agent travel planning system.
Decide which specialist agents are needed for this user request.

Available agents:
- flight_agent: flights, airports, airlines, routes or airfare guidance
- hotel_agent: hotels, stays, neighbourhoods or accommodation
- weather_agent: weather, climate, season, packing or forecast
- budget_agent: budget, affordability, cost or price constraints
- itinerary_agent: always needed to produce the travel plan

Return only JSON with this schema:
{{
  "selected_agents": ["flight_agent", "hotel_agent", "weather_agent", "budget_agent", "itinerary_agent"],
  "trip_constraints": {{
    "destination": "", "origin": "", "duration": "", "budget": "",
    "travel_style": "", "special_preferences": []
  }},
  "reasoning": ""
}}

User request:
{query}
"""


class LLMRoutingStrategy(RoutingStrategy):
    name = "llm"

    def __init__(self, llm: LLMClient):
        self._llm = llm

    def route(self, query: str) -> RoutingDecision:
        answer = self._llm.complete(ROUTING_SYSTEM_PROMPT, ROUTING_PROMPT.format(query=query))
        data = extract_json_object(answer)

        agents = data.get("selected_agents")
        if not isinstance(agents, list):
            raise LLMResponseFormatError("'selected_agents' must be a list", raw_response=answer)

        constraints = data.get("trip_constraints")
        if not isinstance(constraints, dict):
            constraints = {}

        return RoutingDecision(
            selected_agents=AgentName.parse_many(agents),
            constraints=TripConstraints.from_mapping(constraints),
            reasoning=str(data.get("reasoning", "")),
            strategy_name=self.name,
        )


# --------------------------------------------------------------------------- keyword strategy
AGENT_KEYWORDS = {
    AgentName.FLIGHT: ["flight", "fly", "airline", "airport", "airfare"],
    AgentName.HOTEL: ["hotel", "stay", "accommodation", "hostel", "resort", "airbnb", "lodging"],
    AgentName.WEATHER: ["weather", "climate", "season", "forecast", "packing", "temperature", "rain"],
}
BUDGET_KEYWORDS = ["budget", "cost", "price", "afford", "cheap", "expense"]
COMPLETE_TRIP_WORDS = ["complete", "full", "entire", "everything", "whole"]

BUDGET_STYLE_WORDS = ["budget hotel", "budget travel", "budget trip", "cheap", "backpack", "hostel", "low-cost"]
LUXURY_STYLE_WORDS = ["luxury", "luxurious", "5-star", "five star", "premium", "high-end"]

NOT_PLACES = {
    "January", "February", "March", "April", "May", "June", "July", "August", "September",
    "October", "November", "December", "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday", "Summer", "Winter", "Spring", "Autumn",
}

PLACE = r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)"  # one or two capitalised words, e.g. "New York"
DESTINATION_AFTER_WORD = re.compile(r"\b(?:to|in|visit|visiting|explore)\s+(?:the\s+)?" + PLACE)
DESTINATION_BEFORE_TRIP = re.compile(PLACE + r"\s+(?:trip|tour|vacation|holiday|getaway)\b")
ORIGIN_PATTERN = re.compile(r"\bfrom\s+" + PLACE)
BUDGET_PATTERN = re.compile(
    r"\b(?:under|within|below|budget of|max|maximum|up to)\s+"
    r"((?:rs\.?|pkr|usd|\$|€|£)?\s*\d[\d,.]*"
    r"(?:\s*(?:k|lakhs?|lacs?|crores?|thousand|million)\b)?"
    r"(?:\s*(?:rs|pkr|usd|dollars|rupees|euros?|eur|gbp|aed)\b)?)",
    re.IGNORECASE,
)


def contains_word(text: str, words: list[str]) -> bool:
    """True if any of the words starts a word in the text ("flight" also matches "flights")."""
    for word in words:
        if re.search(r"\b" + re.escape(word), text):
            return True
    return False


class KeywordRoutingStrategy(RoutingStrategy):
    name = "keyword"

    def route(self, query: str) -> RoutingDecision:
        lowered = query.lower()
        budget_text = self.find_budget(query)

        agents = []
        for agent, words in AGENT_KEYWORDS.items():
            if contains_word(lowered, words):
                agents.append(agent)
        if not agents or contains_word(lowered, COMPLETE_TRIP_WORDS):
            agents = list(RESEARCH_AGENTS)  # a general trip request needs all research
        if budget_text or contains_word(lowered, BUDGET_KEYWORDS):
            agents.append(AgentName.BUDGET)

        constraints = TripConstraints.from_mapping({
            "destination": self.find_destination(query),
            "origin": self.find_origin(query),
            "duration": parse_duration_days(query),
            "budget": budget_text,
            "travel_style": self.find_travel_style(lowered).value,
        })
        names = ", ".join(agent.value for agent in agents)
        return RoutingDecision(
            selected_agents=tuple(agents),
            constraints=constraints,
            reasoning=f"Rule-based routing selected: {names}",
            strategy_name=self.name,
        )

    @staticmethod
    def find_destination(query: str) -> str:
        for match in DESTINATION_AFTER_WORD.finditer(query):
            if match.group(1) not in NOT_PLACES:
                return match.group(1)
        match = DESTINATION_BEFORE_TRIP.search(query)
        if match and match.group(1) not in NOT_PLACES:
            return match.group(1)
        return ""

    @staticmethod
    def find_origin(query: str) -> str:
        match = ORIGIN_PATTERN.search(query)
        return match.group(1) if match else ""

    @staticmethod
    def find_budget(query: str) -> str:
        match = BUDGET_PATTERN.search(query)
        if match is None:
            return ""
        return match.group(1).strip().rstrip(".,")

    @staticmethod
    def find_travel_style(lowered_query: str) -> TravelStyle:
        if contains_word(lowered_query, BUDGET_STYLE_WORDS):
            return TravelStyle.BUDGET
        if contains_word(lowered_query, LUXURY_STYLE_WORDS):
            return TravelStyle.LUXURY
        return TravelStyle.MID_RANGE


# --------------------------------------------------------------------------- fallback strategy
# Strategy pattern: combines two strategies - the LLM first, keyword rules if the LLM fails.
class FallbackRoutingStrategy(RoutingStrategy):
    """Uses the primary strategy, and the fallback strategy if the primary fails."""

    def __init__(self, primary: RoutingStrategy, fallback: RoutingStrategy):
        self._primary = primary
        self._fallback = fallback
        self.name = f"{primary.name} with {fallback.name} fallback"

    def route(self, query: str) -> RoutingDecision:
        try:
            return self._primary.route(query)
        except (LLMResponseFormatError, ExternalServiceError) as error:
            logger.warning("Primary routing failed (%s); using %s routing", error, self._fallback.name)

        decision = self._fallback.route(query)
        return RoutingDecision(
            selected_agents=decision.selected_agents,
            constraints=decision.constraints,
            reasoning=decision.reasoning,
            strategy_name=f"{self._fallback.name} (fallback)",
        )
