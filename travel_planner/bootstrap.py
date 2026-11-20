"""Composition root: the one place where all objects are created and connected.

Every class receives its dependencies through its constructor (Dependency
Injection), so no class creates its own collaborators with hidden globals.
This replaces the prototype's module-level `llm = get_llm()` and MCP client,
which ran at import time and made testing impossible without API keys.
"""

import atexit
import logging

from dotenv import load_dotenv

from travel_planner.factories import IntegrationFactory, create_integration_factory
from travel_planner.intake.guardrail import LLMInputGuardrail
from travel_planner.intake.routing import FallbackRoutingStrategy, KeywordRoutingStrategy, LLMRoutingStrategy
from travel_planner.intake.service import IntakeService
from travel_planner.intake.validation import RequestValidator
from travel_planner.llm.decorators import LoggingLLMClient, RetryingLLMClient
from travel_planner.llm.groq_adapter import GroqChatAdapter
from travel_planner.llm.ports import LLMClient
from travel_planner.planning.budget import BudgetAnalyzer
from travel_planner.planning.budget_parser import BudgetParser
from travel_planner.planning.budget_report import BudgetAdvisor, BudgetReportFormatter
from travel_planner.planning.destinations import DestinationCatalog
from travel_planner.planning.money import CurrencyConverter
from travel_planner.planning.itinerary import FinalPlanComposer, ItineraryPlanner
from travel_planner.research.agents import FlightResearchAgent, HotelResearchAgent, WeatherResearchAgent
from travel_planner.research.coordinator import ResearchCoordinator
from travel_planner.settings import Settings
from travel_planner.workflow.approval import RevisionPolicy
from travel_planner.workflow.facade import TravelPlanningFacade
from travel_planner.workflow.graph import build_planning_graph
from travel_planner.workflow.nodes import PlanningNodes


def build_facade() -> TravelPlanningFacade:
    """Create the real application from the .env file."""
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    # Decorator pattern: retries and logging are stacked around the Groq adapter.
    llm = RetryingLLMClient(LoggingLLMClient(GroqChatAdapter(settings.groq_model, settings.groq_api_key)))
    # Abstract Factory pattern: one call chooses the live or the sample family of objects.
    factory = create_integration_factory(settings)
    atexit.register(factory.close)  # close the database pool cleanly when the program stops
    return assemble_facade(settings, llm, factory)


def assemble_facade(settings: Settings, llm: LLMClient, factory: IntegrationFactory) -> TravelPlanningFacade:
    """Wire all modules together. Tests call this with a fake LLM."""
    # Module 1 - intake (Strategy pattern: LLM routing with keyword routing as the fallback)
    intake = IntakeService(
        RequestValidator(),
        LLMInputGuardrail(llm),
        FallbackRoutingStrategy(primary=LLMRoutingStrategy(llm), fallback=KeywordRoutingStrategy()),
    )

    # Module 2 - research (products of the chosen integration family)
    research = ResearchCoordinator(
        [
            FlightResearchAgent(factory.create_flight_provider(), llm),
            HotelResearchAgent(factory.create_hotel_provider(), llm),
            WeatherResearchAgent(factory.create_weather_provider()),
        ],
        timeout_seconds=settings.research_timeout_seconds,
    )

    # Module 3 - planning (DIP: every helper is created here and injected)
    converter = CurrencyConverter()
    budget_advisor = BudgetAdvisor(
        BudgetAnalyzer(BudgetParser(), converter, DestinationCatalog()),
        BudgetReportFormatter(converter),
        llm,
    )

    # Module 4 - workflow and persistence
    plan_store = factory.create_plan_store()
    nodes = PlanningNodes(
        intake=intake,
        research=research,
        budget_advisor=budget_advisor,
        itinerary_planner=ItineraryPlanner(llm),
        final_composer=FinalPlanComposer(llm),
        revision_policy=RevisionPolicy(settings.max_revisions),
        plan_repository=plan_store,
        audit_log=plan_store,
    )
    graph = build_planning_graph(nodes, factory.create_checkpointer())
    # Facade pattern: the UI receives one simple object and never sees LangGraph.
    return TravelPlanningFacade(graph, plan_store)
