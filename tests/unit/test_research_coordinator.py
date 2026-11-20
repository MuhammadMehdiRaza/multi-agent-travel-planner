import threading
import time

from travel_planner.domain.models import AgentName, TripConstraints
from travel_planner.research.agents import ResearchAgent
from travel_planner.research.coordinator import ResearchCoordinator
from travel_planner.shared.exceptions import ExternalServiceError

A = AgentName
CONSTRAINTS = TripConstraints(destination="Tokyo")


class SlowAgent(ResearchAgent):
    """Test agent that sleeps, then answers (or raises)."""

    def __init__(self, name, seconds=0.0, error=None):
        self.name = name
        self.seconds = seconds
        self.error = error
        self.thread_names = []

    def research(self, query, constraints):
        self.thread_names.append(threading.current_thread().name)
        time.sleep(self.seconds)
        if self.error:
            raise self.error
        return f"{self.name.value} result for {constraints.destination}"


def make_coordinator(*agents, timeout=5.0):
    return ResearchCoordinator(list(agents), timeout_seconds=timeout)


def test_selected_agents_run_in_parallel():
    agents = [SlowAgent(A.FLIGHT, 0.4), SlowAgent(A.HOTEL, 0.4), SlowAgent(A.WEATHER, 0.4)]
    start = time.perf_counter()
    findings = make_coordinator(*agents).run([A.FLIGHT, A.HOTEL, A.WEATHER], "q", CONSTRAINTS)
    elapsed = time.perf_counter() - start

    assert elapsed < 0.9  # sequential execution would take at least 1.2 s
    assert all(finding.succeeded for finding in findings.values())
    assert findings[A.HOTEL].summary == "hotel_agent result for Tokyo"
    assert all(agent.thread_names[0].startswith("research") for agent in agents)


def test_only_selected_research_agents_run():
    flight, hotel = SlowAgent(A.FLIGHT), SlowAgent(A.HOTEL)
    findings = make_coordinator(flight, hotel).run([A.HOTEL, A.BUDGET, A.ITINERARY], "q", CONSTRAINTS)
    assert set(findings) == {A.HOTEL}
    assert flight.thread_names == []


def test_no_selected_agents_returns_empty_result():
    assert make_coordinator(SlowAgent(A.FLIGHT)).run([], "q", CONSTRAINTS) == {}


def test_one_failing_agent_does_not_affect_the_others():
    findings = make_coordinator(
        SlowAgent(A.FLIGHT, error=ExternalServiceError("aviationstack", "quota exceeded")),
        SlowAgent(A.WEATHER),
    ).run([A.FLIGHT, A.WEATHER], "q", CONSTRAINTS)

    assert not findings[A.FLIGHT].succeeded
    assert "quota exceeded" in findings[A.FLIGHT].error
    assert findings[A.WEATHER].succeeded


def test_unexpected_exception_becomes_a_failed_finding():
    findings = make_coordinator(SlowAgent(A.HOTEL, error=KeyError("list"))).run([A.HOTEL], "q", CONSTRAINTS)
    assert not findings[A.HOTEL].succeeded
    assert findings[A.HOTEL].error == "unexpected internal error"


def test_slow_agent_times_out_without_blocking_the_workflow():
    start = time.perf_counter()
    findings = make_coordinator(SlowAgent(A.FLIGHT, 2.0), SlowAgent(A.WEATHER, 0.0), timeout=0.3).run(
        [A.FLIGHT, A.WEATHER], "q", CONSTRAINTS
    )
    assert time.perf_counter() - start < 1.0
    assert not findings[A.FLIGHT].succeeded
    assert "no answer within" in findings[A.FLIGHT].error
    assert findings[A.WEATHER].succeeded


def test_findings_are_returned_in_selection_order():
    findings = make_coordinator(SlowAgent(A.WEATHER, 0.0), SlowAgent(A.FLIGHT, 0.2)).run(
        [A.FLIGHT, A.WEATHER], "q", CONSTRAINTS
    )
    assert list(findings) == [A.FLIGHT, A.WEATHER]
