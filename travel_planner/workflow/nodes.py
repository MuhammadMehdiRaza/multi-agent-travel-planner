"""LangGraph nodes: thin functions that connect the graph state to the module services.

Each node (1) reads what it needs from the state, (2) calls ONE service from a
module, and (3) returns the state fields it changed. No business rules live
here; they are in the modules, where they are unit-tested without LangGraph.
"""

import logging

from langgraph.types import interrupt

from travel_planner.domain.models import AgentName, TripConstraints
from travel_planner.intake.service import IntakeService
from travel_planner.planning.budget_report import BudgetAdvisor
from travel_planner.planning.itinerary import FinalPlanComposer, ItineraryPlanner
from travel_planner.research.coordinator import ResearchCoordinator
from travel_planner.shared.exceptions import PersistenceError
from travel_planner.workflow.approval import ApprovalDecision, NextStep, RevisionPolicy
from travel_planner.workflow.plan_store import ApprovalAuditLog, TripPlanRecord, TripPlanRepository
from travel_planner.workflow.state import TravelState

logger = logging.getLogger(__name__)

# Which state field holds each research agent's result, and its heading in the UI.
RESEARCH_FIELDS = {
    AgentName.FLIGHT: ("flight_results", "Flights"),
    AgentName.HOTEL: ("hotel_results", "Hotels"),
    AgentName.WEATHER: ("weather_results", "Weather"),
}


# SOLID - SRP: each step only passes workflow state to one module service.
# SOLID - DIP: all module services and stores are injected by the composition root.
class PlanningNodes:
    def __init__(
        self,
        intake: IntakeService,
        research: ResearchCoordinator,
        budget_advisor: BudgetAdvisor,
        itinerary_planner: ItineraryPlanner,
        final_composer: FinalPlanComposer,
        revision_policy: RevisionPolicy,
        plan_repository: TripPlanRepository,
        audit_log: ApprovalAuditLog,
    ):
        self._intake = intake
        self._research = research
        self._budget_advisor = budget_advisor
        self._itinerary_planner = itinerary_planner
        self._final_composer = final_composer
        self._revision_policy = revision_policy
        self._plan_repository = plan_repository
        self._audit_log = audit_log

    # ------------------------------------------------------------------ Module 1
    def intake(self, state: TravelState) -> dict:
        outcome = self._intake.process(state["user_query"])
        if not outcome.accepted:
            return {"intake_accepted": False, "rejection_reason": outcome.rejection_reason}

        decision = outcome.decision
        return {
            "intake_accepted": True,
            "user_query": outcome.query,
            "selected_agents": [agent.value for agent in decision.selected_agents],
            "trip_constraints": decision.constraints.to_dict(),
            "supervisor_reasoning": decision.reasoning,
            "routing_strategy": decision.strategy_name,
            "revision_count": 0,
        }

    # ------------------------------------------------------------------ Module 2
    def research(self, state: TravelState) -> dict:
        selected = list(AgentName.parse_many(state.get("selected_agents", [])))
        findings = self._research.run(selected, state["user_query"], constraints_from(state))

        update = {"research_failures": []}
        for agent, finding in findings.items():
            field_name = RESEARCH_FIELDS[agent][0]
            update[field_name] = finding.display_text()
            if not finding.succeeded:
                update["research_failures"].append(agent.label)
        return update

    # ------------------------------------------------------------------ Module 3
    def budget(self, state: TravelState) -> dict:
        advice = self._budget_advisor.advise(
            state["user_query"], constraints_from(state), research_sections(state)
        )
        return {"budget_results": advice.report, "budget_verdict": advice.assessment.verdict.value}

    def draft_itinerary(self, state: TravelState) -> dict:
        feedback = state.get("human_feedback", "") if state.get("revision_count", 0) > 0 else ""
        itinerary = self._itinerary_planner.draft(
            state["user_query"],
            constraints_from(state),
            research_sections(state),
            state.get("budget_results", ""),
            feedback=feedback,
        )
        return {"itinerary": itinerary}

    def finalize(self, state: TravelState) -> dict:
        approved = state.get("approved", False)
        final_plan = self._final_composer.compose(
            state["user_query"],
            state.get("itinerary", ""),
            state.get("budget_results", ""),
            approved=approved,
            feedback=state.get("human_feedback", ""),
        )
        record = TripPlanRecord.create(
            thread_id=state.get("thread_id", ""),
            user_id=state.get("user_id", ""),
            user_query=state["user_query"],
            destination=constraints_from(state).destination,
            approved=approved,
            revision_count=state.get("revision_count", 0),
            budget_verdict=state.get("budget_verdict", "NOT_REQUESTED"),
            final_plan=final_plan,
        )
        try:
            self._plan_repository.save_plan(record)
        except PersistenceError as error:
            # The user still gets the plan; only the history entry is missing.
            logger.error("Could not save plan %s: %s", record.plan_id, error)
            return {"final_response": final_plan, "plan_id": "",
                    "storage_warning": "The plan was created but could not be saved to your history."}
        return {"final_response": final_plan, "plan_id": record.plan_id, "storage_warning": ""}

    # ------------------------------------------------------------------ Module 4
    def human_approval(self, state: TravelState) -> dict:
        # interrupt() pauses the graph here; it continues when the facade resumes it with an answer.
        answer = interrupt({
            "question": "Do you approve this itinerary?",
            "draft_itinerary": state.get("itinerary", ""),
            "revision_count": state.get("revision_count", 0),
        })
        decision = ApprovalDecision.from_payload(answer)
        self._audit_log.record_decision(state.get("thread_id", ""), decision.approved, decision.feedback)

        revisions_done = state.get("revision_count", 0)
        next_step = self._revision_policy.next_step(decision, revisions_done)
        update = {
            "approved": decision.approved,
            "human_feedback": decision.feedback,
            "next_step": next_step.value,
        }
        if next_step is NextStep.REVISE:
            update["revision_count"] = revisions_done + 1
        return update


# ---------------------------------------------------------------------- routing between nodes
def route_after_intake(state: TravelState) -> str:
    return "research" if state.get("intake_accepted") else "rejected"


def route_after_research(state: TravelState) -> str:
    if AgentName.BUDGET.value in state.get("selected_agents", []):
        return "budget"
    return "draft_itinerary"


def route_after_approval(state: TravelState) -> str:
    return "draft_itinerary" if state.get("next_step") == NextStep.REVISE.value else "finalize"


# ---------------------------------------------------------------------- helpers
def constraints_from(state: TravelState) -> TripConstraints:
    return TripConstraints.from_mapping(state.get("trip_constraints", {}))


def research_sections(state: TravelState) -> dict:
    """{"Flights": "...", ...} for the research that was actually done."""
    sections = {}
    for field_name, heading in RESEARCH_FIELDS.values():
        if state.get(field_name):
            sections[heading] = state[field_name]
    return sections
