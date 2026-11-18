import pytest
import requests

import weather_mcp_server as server


class FakeResponse:
    def __init__(self, status_code, data):
        self.status_code = status_code
        self._data = data

    def json(self):
        return self._data


CURRENT_OK = {
    "name": "Rome",
    "main": {"temp": 24.1, "feels_like": 25.0, "humidity": 40},
    "weather": [{"description": "clear sky"}],
    "wind": {"speed": 3.2},
}
FORECAST_OK = {
    "list": [
        {"dt_txt": f"2026-10-0{i} 12:00:00", "main": {"temp": 20 + i}, "weather": [{"description": "rain"}]}
        for i in range(1, 9)
    ]
}


@pytest.fixture
def fake_get(monkeypatch):
    calls = []

    def install(response=None, error=None):
        def fake(url, params, timeout):
            calls.append({"url": url, "params": params, "timeout": timeout})
            if error:
                raise error
            return response

        monkeypatch.setattr(server.requests, "get", fake)
        return calls

    return install


def test_current_weather_is_simplified(fake_get):
    calls = fake_get(FakeResponse(200, CURRENT_OK))
    result = server.get_current_weather("Rome")
    assert result == {
        "city": "Rome", "temperature_c": 24.1, "feels_like_c": 25.0,
        "humidity": 40, "condition": "clear sky", "wind_speed": 3.2,
    }
    assert calls[0]["timeout"] == server.HTTP_TIMEOUT_SECONDS


def test_forecast_returns_first_five_entries(fake_get):
    fake_get(FakeResponse(200, FORECAST_OK))
    result = server.get_forecast("Rome")
    assert len(result["forecast"]) == 5
    assert result["forecast"][0] == {"datetime": "2026-10-01 12:00:00", "temperature": 21, "weather": "rain"}


def test_api_error_is_returned_as_error_message(fake_get):
    fake_get(FakeResponse(404, {"cod": "404", "message": "city not found"}))
    assert server.get_forecast("Atlantis") == {"error": "OpenWeatherMap error 404: city not found"}


def test_network_failure_is_returned_as_error_message(fake_get):
    fake_get(error=requests.exceptions.ConnectTimeout("timed out"))
    assert "could not reach OpenWeatherMap" in server.get_current_weather("Rome")["error"]


def test_unexpected_payload_is_reported(fake_get):
    fake_get(FakeResponse(200, {"unexpected": True}))
    assert "unexpected response" in server.get_current_weather("Rome")["error"]


@pytest.mark.parametrize("city", ["", "   ", "x" * 101])
def test_invalid_city_is_rejected_without_http_call(fake_get, city):
    calls = fake_get(FakeResponse(200, CURRENT_OK))
    assert "error" in server.get_current_weather(city)
    assert calls == []


class NotJsonResponse(FakeResponse):
    def json(self):
        raise ValueError("Expecting value")


def test_error_page_that_is_not_json_is_reported(fake_get):
    fake_get(NotJsonResponse(502, None))
    assert server.get_current_weather("Rome") == {"error": "OpenWeatherMap returned an unreadable answer (HTTP 502)"}
