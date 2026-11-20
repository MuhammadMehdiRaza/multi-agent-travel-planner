"""Offline sample-data providers.

Used in "sample" mode so the whole system can be run and demonstrated with
only a Groq key - without the AviationStack/Weather MCP servers, which the
prototype expected at fixed paths on one team member's laptop. Every answer
is clearly labelled as sample data.
"""

from travel_planner.research.ports import FlightDataProvider, HotelSearchProvider, WeatherProvider

LABEL = "[SAMPLE DATA - not live]"


# SOLID - LSP: the sample providers can replace the MCP adapters anywhere (offline sample mode).
class SampleFlightData(FlightDataProvider):
    def departures(self, airport_code: str, limit: int = 10) -> str:
        return (f"{LABEL} Departures from {airport_code} today: Emirates to DXB, Qatar Airways to DOH, "
                "Turkish Airlines to IST, PIA to JED.")


class SampleHotelData(HotelSearchProvider):
    def search_hotels(self, query: str) -> str:
        return (
            f"{LABEL} Search: {query}\n"
            "- City-centre business hotel, about USD 90 per night\n"
            "- Budget hostel near the main station, about USD 30 per night\n"
            "- Boutique hotel in the old town, about USD 150 per night"
        )


class SampleWeatherData(WeatherProvider):
    def current_conditions(self, city: str) -> str:
        return f"{LABEL} {city}: 22 C, feels like 21 C, humidity 60%, scattered clouds."

    def forecast(self, city: str) -> str:
        return f"{LABEL} {city}: next 5 days 18-25 C, light rain expected on day 3."
