"""Weather MCP server: exposes OpenWeatherMap through two MCP tools.

Run on its own with:  python weather_mcp_server.py
(The travel planner starts it automatically in live mode.)

Defensive changes compared with the prototype:
  * every HTTP request has a timeout (the prototype could hang forever)
  * the city name is validated before any HTTP call
  * API errors and unexpected payloads return {"error": ...} instead of crashing with KeyError
"""

import os

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

BASE_URL = "https://api.openweathermap.org/data/2.5"
HTTP_TIMEOUT_SECONDS = 10
MAX_CITY_LENGTH = 100
FORECAST_ENTRIES = 5

mcp = FastMCP("Weather Server")


class WeatherApiError(Exception):
    """Raised inside this module when OpenWeatherMap cannot give a usable answer."""


def fetch_json(endpoint: str, city: str) -> dict:
    params = {"q": city, "appid": os.getenv("OPENWEATHER_API_KEY", ""), "units": "metric"}
    try:
        response = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=HTTP_TIMEOUT_SECONDS)
    except requests.exceptions.RequestException as error:
        raise WeatherApiError(f"could not reach OpenWeatherMap ({type(error).__name__})") from error

    try:
        data = response.json()
    except ValueError as error:  # e.g. an HTML error page from a proxy
        message = f"OpenWeatherMap returned an unreadable answer (HTTP {response.status_code})"
        raise WeatherApiError(message) from error
    if response.status_code != 200:
        message = data.get("message", "unknown error") if isinstance(data, dict) else "unknown error"
        raise WeatherApiError(f"OpenWeatherMap error {response.status_code}: {message}")
    return data


def validate_city(city: str) -> str:
    city = (city or "").strip()
    if not city or len(city) > MAX_CITY_LENGTH:
        raise WeatherApiError(f"city must be 1-{MAX_CITY_LENGTH} characters")
    return city


@mcp.tool()
def get_current_weather(city: str) -> dict:
    """Current temperature, humidity, wind and conditions for a city."""
    try:
        data = fetch_json("weather", validate_city(city))
        return {
            "city": data["name"],
            "temperature_c": data["main"]["temp"],
            "feels_like_c": data["main"]["feels_like"],
            "humidity": data["main"]["humidity"],
            "condition": data["weather"][0]["description"],
            "wind_speed": data["wind"]["speed"],
        }
    except WeatherApiError as error:
        return {"error": str(error)}
    except (KeyError, IndexError, TypeError):
        return {"error": "unexpected response format from OpenWeatherMap"}


@mcp.tool()
def get_forecast(city: str) -> dict:
    """The next few 3-hourly forecast entries for a city."""
    try:
        city = validate_city(city)
        data = fetch_json("forecast", city)
        forecast = []
        for item in data["list"][:FORECAST_ENTRIES]:
            forecast.append({
                "datetime": item["dt_txt"],
                "temperature": item["main"]["temp"],
                "weather": item["weather"][0]["description"],
            })
        return {"city": city, "forecast": forecast}
    except WeatherApiError as error:
        return {"error": str(error)}
    except (KeyError, IndexError, TypeError):
        return {"error": "unexpected response format from OpenWeatherMap"}


if __name__ == "__main__":
    mcp.run()
