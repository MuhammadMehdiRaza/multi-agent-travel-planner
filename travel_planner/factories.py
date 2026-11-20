"""Abstract Factory pattern: create a matching FAMILY of integration objects.

    AbstractFactory   = IntegrationFactory
    ConcreteFactories = LiveIntegrationFactory   (real MCP servers + PostgreSQL)
                        SampleIntegrationFactory (offline sample data + SQLite)
    Products          = flight / hotel / weather providers, plan store, checkpointer

Why a family? The products must never be mixed. For example, sample (fake)
weather data saved into the live PostgreSQL history would corrupt real users'
plans. Choosing ONE factory guarantees all products come from the same family.
The family is chosen in exactly one place: create_integration_factory().
"""

from abc import ABC, abstractmethod

from travel_planner.research.mcp_adapters import McpFlightDataAdapter, McpHotelSearchAdapter, McpWeatherAdapter
from travel_planner.research.mcp_gateway import McpToolGateway, live_mcp_connections
from travel_planner.research.ports import FlightDataProvider, HotelSearchProvider, WeatherProvider
from travel_planner.research.sample_data import SampleFlightData, SampleHotelData, SampleWeatherData
from travel_planner.settings import Settings
from travel_planner.workflow.plan_store import SqlitePlanStore, SqlPlanStore


# Design pattern: Abstract Factory (creational) - one factory creates a whole compatible family.
# SOLID - OCP: a new environment (e.g. a cloud family) is a new factory subclass; no client changes.
# SOLID - LSP: LiveIntegrationFactory and SampleIntegrationFactory are interchangeable.
class IntegrationFactory(ABC):
    def __init__(self, settings: Settings):
        self._settings = settings

    @abstractmethod
    def create_flight_provider(self) -> FlightDataProvider:
        """Flight data of this family (MCP adapter or sample data)."""

    @abstractmethod
    def create_hotel_provider(self) -> HotelSearchProvider:
        """Hotel search of this family."""

    @abstractmethod
    def create_weather_provider(self) -> WeatherProvider:
        """Weather data of this family."""

    @abstractmethod
    def create_plan_store(self) -> SqlPlanStore:
        """Database for plans and approval decisions (PostgreSQL or SQLite)."""

    @abstractmethod
    def create_checkpointer(self):
        """Storage LangGraph uses to pause/resume the workflow."""

    def close(self) -> None:
        """Release shared resources (database pool) when the application stops.

        The sample family holds no shared resources, so the base version has nothing to release.
        """


class LiveIntegrationFactory(IntegrationFactory):
    def __init__(self, settings: Settings):
        super().__init__(settings)
        # One gateway shared by all adapters, so the MCP tools are loaded only once.
        self._gateway = McpToolGateway(self._create_mcp_client, call_timeout_seconds=settings.research_timeout_seconds)
        self._pool = None

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None

    def _create_mcp_client(self):
        from langchain_mcp_adapters.client import MultiServerMCPClient  # pylint: disable=import-outside-toplevel

        return MultiServerMCPClient(live_mcp_connections(self._settings))

    def _connection_pool(self):
        if self._pool is None:
            from psycopg.rows import dict_row  # pylint: disable=import-outside-toplevel
            from psycopg_pool import ConnectionPool  # pylint: disable=import-outside-toplevel

            # Settings required by LangGraph's PostgresSaver: autocommit + dict rows.
            self._pool = ConnectionPool(
                conninfo=self._settings.database_url,
                max_size=10,
                kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
                open=True,
            )
        return self._pool

    def create_flight_provider(self) -> FlightDataProvider:
        return McpFlightDataAdapter(self._gateway)

    def create_hotel_provider(self) -> HotelSearchProvider:
        return McpHotelSearchAdapter(self._gateway)

    def create_weather_provider(self) -> WeatherProvider:
        return McpWeatherAdapter(self._gateway)

    def create_plan_store(self) -> SqlPlanStore:
        from travel_planner.workflow.postgres_store import PostgresPlanStore  # pylint: disable=import-outside-toplevel

        return PostgresPlanStore(self._connection_pool())

    def create_checkpointer(self):
        from langgraph.checkpoint.postgres import PostgresSaver  # pylint: disable=import-outside-toplevel

        checkpointer = PostgresSaver(self._connection_pool())
        checkpointer.setup()  # creates LangGraph's checkpoint tables if needed
        return checkpointer


class SampleIntegrationFactory(IntegrationFactory):
    def create_flight_provider(self) -> FlightDataProvider:
        return SampleFlightData()

    def create_hotel_provider(self) -> HotelSearchProvider:
        return SampleHotelData()

    def create_weather_provider(self) -> WeatherProvider:
        return SampleWeatherData()

    def create_plan_store(self) -> SqlPlanStore:
        return SqlitePlanStore(self._settings.sqlite_path)

    def create_checkpointer(self):
        from langgraph.checkpoint.memory import InMemorySaver  # pylint: disable=import-outside-toplevel

        return InMemorySaver()


def create_integration_factory(settings: Settings) -> IntegrationFactory:
    """The ONLY place that decides which family is used (DATA_SOURCE in .env)."""
    if settings.data_source == "live":
        return LiveIntegrationFactory(settings)
    return SampleIntegrationFactory(settings)
