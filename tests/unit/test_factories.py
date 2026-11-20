from langgraph.checkpoint.memory import InMemorySaver

from travel_planner.factories import (
    LiveIntegrationFactory,
    SampleIntegrationFactory,
    create_integration_factory,
)
from travel_planner.research.mcp_adapters import McpFlightDataAdapter, McpHotelSearchAdapter, McpWeatherAdapter
from travel_planner.research.sample_data import SampleFlightData, SampleHotelData, SampleWeatherData
from travel_planner.settings import Settings
from travel_planner.workflow.plan_store import SqlitePlanStore

LIVE_ENV = {
    "GROQ_API_KEY": "g", "DATA_SOURCE": "live", "TAVILY_API_KEY": "t", "AVIATION_STACK_API_KEY": "a",
    "OPENWEATHER_API_KEY": "o", "DATABASE_URL": "postgresql://localhost/db", "AVIATIONSTACK_MCP_PYTHON": "py",
}


def test_sample_mode_selects_the_sample_family(tmp_path):
    settings = Settings.from_env({"GROQ_API_KEY": "g", "SQLITE_PATH": str(tmp_path / "p.sqlite3")})
    factory = create_integration_factory(settings)

    assert isinstance(factory, SampleIntegrationFactory)
    assert isinstance(factory.create_flight_provider(), SampleFlightData)
    assert isinstance(factory.create_hotel_provider(), SampleHotelData)
    assert isinstance(factory.create_weather_provider(), SampleWeatherData)
    assert isinstance(factory.create_plan_store(), SqlitePlanStore)
    assert isinstance(factory.create_checkpointer(), InMemorySaver)


def test_live_mode_selects_the_live_family_without_connecting():
    factory = create_integration_factory(Settings.from_env(LIVE_ENV))

    assert isinstance(factory, LiveIntegrationFactory)
    # creating adapters must not start MCP servers yet (tools load lazily on first call)
    assert isinstance(factory.create_flight_provider(), McpFlightDataAdapter)
    assert isinstance(factory.create_hotel_provider(), McpHotelSearchAdapter)
    assert isinstance(factory.create_weather_provider(), McpWeatherAdapter)


def test_live_adapters_share_one_mcp_gateway():
    factory = LiveIntegrationFactory(Settings.from_env(LIVE_ENV))
    flights = factory.create_flight_provider()
    weather = factory.create_weather_provider()
    assert flights._gateway is weather._gateway  # pylint: disable=protected-access


class FakePool:
    def __init__(self):
        self.closed = 0

    def close(self):
        self.closed += 1


def test_live_factory_close_releases_the_database_pool_once():
    factory = LiveIntegrationFactory(Settings.from_env(LIVE_ENV))
    pool = FakePool()
    factory._pool = pool  # pylint: disable=protected-access
    factory.close()
    factory.close()  # closing twice is safe
    assert pool.closed == 1


def test_sample_factory_close_is_safe(tmp_path):
    settings = Settings.from_env({"GROQ_API_KEY": "g", "SQLITE_PATH": str(tmp_path / "p.sqlite3")})
    create_integration_factory(settings).close()
