"""Runs the selected research agents concurrently (the system's concurrent operation).

The prototype ran flight -> hotel -> weather one after another, so the user
waited for the SUM of three slow network calls. They are independent, so they
now run at the same time on a thread pool and the user waits for the SLOWEST.

Thread-safety strategy:
  * Inputs are immutable: the query is a str and TripConstraints is frozen.
  * Agents keep no per-request state, so one agent object can be used by any thread.
  * Each worker returns its own ResearchFinding (it never writes shared data);
    only this coordinating thread writes to the `findings` dictionary.
  * The only shared mutable object (the MCP tool cache) is guarded by a lock
    inside McpToolGateway.
  * A time limit stops one slow service from blocking the whole workflow.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from travel_planner.domain.models import AgentName, ResearchFinding, TripConstraints
from travel_planner.research.agents import ResearchAgent
from travel_planner.shared.exceptions import TravelPlannerError

logger = logging.getLogger(__name__)


# Concurrency: the selected agents run in parallel on a thread pool with a time limit.
# Thread safety: agents receive only read-only inputs and share no changeable state.
# SOLID - DIP: works with the ResearchAgent interface; the agents are injected.
class ResearchCoordinator:
    def __init__(self, agents: list[ResearchAgent], timeout_seconds: float = 45.0):
        self._agents = {agent.name: agent for agent in agents}
        self._timeout = timeout_seconds

    def run(self, selected: list[AgentName], query: str, constraints: TripConstraints) -> dict:
        """Run the selected agents in parallel and return {AgentName: ResearchFinding}."""
        jobs = [name for name in selected if name in self._agents]
        if not jobs:
            return {}

        results = {}
        pool = ThreadPoolExecutor(max_workers=len(jobs), thread_name_prefix="research")
        futures = [pool.submit(self._run_agent, self._agents[name], query, constraints) for name in jobs]
        try:
            for future in as_completed(futures, timeout=self._timeout):
                finding = future.result()  # _run_agent never raises
                results[finding.agent] = finding
        except TimeoutError:
            logger.warning("Research did not finish within %.0f seconds", self._timeout)
        finally:
            # Do not wait for a stuck thread; cancel jobs that have not started yet.
            pool.shutdown(wait=False, cancel_futures=True)

        # Return findings in the order the agents were selected; missing ones timed out.
        findings = {}
        for name in jobs:
            if name in results:
                findings[name] = results[name]
            else:
                findings[name] = ResearchFinding.failed(
                    name, f"no answer within {self._timeout:.0f} seconds", self._timeout
                )
        return findings

    @staticmethod
    def _run_agent(agent: ResearchAgent, query: str, constraints: TripConstraints) -> ResearchFinding:
        start = time.perf_counter()
        try:
            summary = agent.research(query, constraints)
            return ResearchFinding(agent.name, summary, elapsed_seconds=time.perf_counter() - start)
        except TravelPlannerError as error:
            logger.warning("%s research failed: %s", agent.name.label, error)
            return ResearchFinding.failed(agent.name, str(error), time.perf_counter() - start)
        except Exception:  # pylint: disable=broad-exception-caught
            # Last-resort guard at the thread boundary: an unexpected bug in one agent
            # must not crash the other agents. The full traceback is logged.
            logger.exception("Unexpected error in %s research", agent.name.label)
            elapsed = time.perf_counter() - start
            return ResearchFinding.failed(agent.name, "unexpected internal error", elapsed)
