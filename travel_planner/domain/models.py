"""Domain value objects shared by all modules.

All classes here are *frozen* dataclasses: after an object is created its
fields cannot be changed. This protects business rules (e.g. a trip must be
1-60 days long) and makes the objects safe to share between threads.
"""

import re
from dataclasses import dataclass
from enum import Enum

from travel_planner.shared.exceptions import ValidationError

MIN_DURATION_DAYS = 1
MAX_DURATION_DAYS = 60

WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

# Matches phrases such as "7 days", "7-day", "10 nights", "two weeks".
DURATION_PATTERN = re.compile(
    r"\b(\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten)\s*-?\s*(day|night|week)s?\b"
)


def parse_duration_days(value) -> int | None:
    """Convert a duration such as "7 days", "2 weeks" or "weekend" into a number of days.

    Returns None when no duration can be recognised.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value

    text = str(value).strip().lower()
    if text.isdigit():
        return int(text)
    if "weekend" in text:
        return 2

    match = DURATION_PATTERN.search(text)
    if match is None:
        return None

    number_text, unit = match.groups()
    if number_text.isdigit():
        number = int(number_text)
    else:
        number = WORD_NUMBERS[number_text]

    if unit == "week":
        return number * 7
    return number


class AgentName(str, Enum):
    """Names of the specialist agents that the supervisor can select."""

    FLIGHT = "flight_agent"
    HOTEL = "hotel_agent"
    WEATHER = "weather_agent"
    BUDGET = "budget_agent"
    ITINERARY = "itinerary_agent"

    @property
    def label(self) -> str:
        """Human readable name, e.g. "Flight"."""
        return self.value.replace("_agent", "").capitalize()

    @classmethod
    def parse_many(cls, values) -> tuple["AgentName", ...]:
        """Convert a list of strings into AgentNames, ignoring unknown names and duplicates."""
        result = []
        for value in values:
            text = str(value).strip().lower()
            for agent in cls:
                if agent.value == text and agent not in result:
                    result.append(agent)
        return tuple(result)


# Agents always run in this order.
AGENT_ORDER = (
    AgentName.FLIGHT,
    AgentName.HOTEL,
    AgentName.WEATHER,
    AgentName.BUDGET,
    AgentName.ITINERARY,
)

# The agents that collect external data and can run at the same time.
RESEARCH_AGENTS = (AgentName.FLIGHT, AgentName.HOTEL, AgentName.WEATHER)


class TravelStyle(str, Enum):
    BUDGET = "budget"
    MID_RANGE = "mid_range"
    LUXURY = "luxury"

    @classmethod
    def parse(cls, text) -> "TravelStyle":
        """Map free text (e.g. "cheap hostels", "5-star") to a travel style. Default: mid-range."""
        text = str(text or "").lower()
        budget_words = ["budget", "cheap", "backpack", "hostel", "economy", "low-cost"]
        luxury_words = ["luxury", "luxurious", "5-star", "five star", "premium", "high-end"]

        for word in budget_words:
            if word in text:
                return cls.BUDGET
        for word in luxury_words:
            if word in text:
                return cls.LUXURY
        return cls.MID_RANGE


def clean_text(value) -> str:
    """Return the value as a stripped string ("" for None)."""
    if value is None:
        return ""
    return str(value).strip()


def clean_preferences(value) -> tuple[str, ...]:
    """Accept a single string or a list of strings and return a tuple of non-empty strings."""
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return ()

    preferences = []
    for item in value:
        text = clean_text(item)
        if text:
            preferences.append(text)
    return tuple(preferences)


@dataclass(frozen=True)
class TripConstraints:
    """Structured constraints extracted from a user's travel request."""

    destination: str = ""
    origin: str = ""
    duration_days: int | None = None
    budget_text: str = ""
    travel_style: TravelStyle = TravelStyle.MID_RANGE
    special_preferences: tuple[str, ...] = ()

    def __post_init__(self):
        # Invariant: a trip is between 1 and 60 days long (or unknown).
        if self.duration_days is None:
            return
        if self.duration_days < MIN_DURATION_DAYS or self.duration_days > MAX_DURATION_DAYS:
            raise ValidationError(
                f"Trip duration must be between {MIN_DURATION_DAYS} and {MAX_DURATION_DAYS} days, "
                f"got {self.duration_days}"
            )

    @classmethod
    def from_mapping(cls, data: dict) -> "TripConstraints":
        """Build constraints from untrusted data (LLM JSON output or graph state).

        LLM output is only advisory, so an impossible duration (e.g. "400 days")
        is dropped instead of crashing the workflow.
        """
        duration = parse_duration_days(data.get("duration_days", data.get("duration")))
        if duration is not None and not MIN_DURATION_DAYS <= duration <= MAX_DURATION_DAYS:
            duration = None

        return cls(
            destination=clean_text(data.get("destination")),
            origin=clean_text(data.get("origin")),
            duration_days=duration,
            budget_text=clean_text(data.get("budget_text", data.get("budget"))),
            travel_style=TravelStyle.parse(data.get("travel_style")),
            special_preferences=clean_preferences(data.get("special_preferences")),
        )

    def to_dict(self) -> dict:
        """Convert to plain values so LangGraph can store it in the checkpoint database."""
        return {
            "destination": self.destination,
            "origin": self.origin,
            "duration_days": self.duration_days,
            "budget_text": self.budget_text,
            "travel_style": self.travel_style.value,
            "special_preferences": list(self.special_preferences),
        }


@dataclass(frozen=True)
class RoutingDecision:
    """The supervisor's plan: which agents should run, and the trip constraints."""

    selected_agents: tuple[AgentName, ...]
    constraints: TripConstraints
    reasoning: str
    strategy_name: str

    def __post_init__(self):
        # Business rule: the itinerary agent always runs, and agents run in AGENT_ORDER.
        wanted = set(self.selected_agents)
        wanted.add(AgentName.ITINERARY)
        ordered = tuple(agent for agent in AGENT_ORDER if agent in wanted)
        # A frozen dataclass cannot use "self.x = ..."; object.__setattr__ is the
        # standard way to set a field while the object is being constructed.
        object.__setattr__(self, "selected_agents", ordered)

    @property
    def research_agents(self) -> tuple[AgentName, ...]:
        """The selected agents that collect external data (flight / hotel / weather)."""
        return tuple(agent for agent in self.selected_agents if agent in RESEARCH_AGENTS)

    def includes(self, agent: AgentName) -> bool:
        return agent in self.selected_agents


@dataclass(frozen=True)
class ResearchFinding:
    """Result of one research agent. A failure is stored as a value instead of crashing."""

    agent: AgentName
    summary: str
    succeeded: bool = True
    error: str = ""
    elapsed_seconds: float = 0.0

    @classmethod
    def failed(cls, agent: AgentName, error: str, elapsed_seconds: float = 0.0) -> "ResearchFinding":
        return cls(agent=agent, summary="", succeeded=False, error=error, elapsed_seconds=elapsed_seconds)

    def display_text(self) -> str:
        if self.succeeded:
            return self.summary
        # The technical error stays in self.error (logged); the user sees a plain sentence.
        return f"_{self.agent.label} research is unavailable right now. The plan continues without it._"
