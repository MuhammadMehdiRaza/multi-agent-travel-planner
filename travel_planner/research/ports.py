"""Small, role-specific interfaces for external travel data (Interface Segregation).

Instead of one big "TravelDataService" with flight + hotel + weather methods,
each research agent depends only on the one role it needs. A weather-only
provider never has to implement (or fake) flight methods.
"""

from abc import ABC, abstractmethod


# SOLID - ISP: three small role interfaces instead of one large travel-data interface,
# so each agent depends only on the methods it uses.
class FlightDataProvider(ABC):
    @abstractmethod
    def departures(self, airport_code: str, limit: int = 10) -> str:
        """Return today's scheduled departures from an airport (IATA code, e.g. "LHE")."""


class HotelSearchProvider(ABC):
    @abstractmethod
    def search_hotels(self, query: str) -> str:
        """Return web search results about hotels and areas to stay."""


class WeatherProvider(ABC):
    @abstractmethod
    def current_conditions(self, city: str) -> str:
        """Return the current weather for a city."""

    @abstractmethod
    def forecast(self, city: str) -> str:
        """Return the short-term forecast for a city."""
