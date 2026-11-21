"""Facade pattern: one simple entry point for the user interface.

Without it, the Streamlit page had to know LangGraph details: thread-id
config dicts, Command(resume=...), the "__interrupt__" key and the exact
names of ~15 state fields. The UI now calls three methods:

    start_planning(user_id, query)          -> PlanningSnapshot
    submit_decision(thread_id, approved, feedback) -> PlanningSnapshot
    history(user_id)                        -> list[TripPlanRecord]

The facade only coordinates; the business rules stay in the modules.
"""

import uuid
from dataclasses import dataclass, field
from enum import Enum

from langgraph.types import Command

from travel_planner.shared.exceptions import InvalidApprovalError, InvalidRequestError
from travel_planner.workflow.approval import ApprovalDecision
from travel_planner.workflow.nodes import RESEARCH_FIELDS
from travel_planner.workflow.plan_store import TripPlanRecord, TripPlanRepository

MAX_USER_ID_LENGTH = 100


class PlanStatus(str, Enum):
    REJECTED = "rejected"                    # the request was not accepted
    AWAITING_APPROVAL = "awaiting_approval"  # a draft is waiting for the user's decision
    COMPLETED = "completed"                  # the final plan is ready


@dataclass(frozen=True)
class PlanningSnapshot:
    """Everything the UI needs to show about one planning session."""

    thread_id: str
    status: PlanStatus
    rejection_reason: str = ""
    supervisor_reasoning: str = ""
    routing_strategy: str = ""
    selected_agents: tuple[str, ...] = ()
    # {"Flights": ..., "Hotels": ..., "Weather": ..., "Budget": ...}
    sections: dict = field(default_factory=dict)
    research_failures: tuple[str, ...] = ()
    budget_verdict: str = ""
    draft_itinerary: str = ""
    revision_count: int = 0
    final_plan: str = ""
    plan_id: str = ""
    storage_warning: str = ""


# Design pattern: Facade (structural) - one simple entry point; the UI never sees LangGraph.
class TravelPlanningFacade:
    def __init__(self, graph, plan_repository: TripPlanRepository):
        self._graph = graph
        self._plans = plan_repository

    def start_planning(self, user_id: str, query: str) -> PlanningSnapshot:
        user_id = validate_user_id(user_id)
        thread_id = f"{user_id}-{uuid.uuid4().hex[:8]}"  # a new session for every request
        self._graph.invoke(
            {"thread_id": thread_id, "user_id": user_id, "user_query": query},
            config=self._config(thread_id),
        )
        return self.snapshot(thread_id)

    def submit_decision(self, thread_id: str, approved: bool, feedback: str) -> PlanningSnapshot:
        decision = ApprovalDecision(approved=approved, feedback=feedback)  # validate BEFORE resuming
        if self.snapshot(thread_id).status is not PlanStatus.AWAITING_APPROVAL:
            raise InvalidApprovalError("This plan is not waiting for approval.")
        self._graph.invoke(Command(resume=decision.to_payload()), config=self._config(thread_id))
        return self.snapshot(thread_id)

    def history(self, user_id: str, limit: int = 10) -> list[TripPlanRecord]:
        return self._plans.plans_for_user(validate_user_id(user_id), limit)

    def snapshot(self, thread_id: str) -> PlanningSnapshot:
        graph_state = self._graph.get_state(self._config(thread_id))
        values = graph_state.values
        if not values:
            raise InvalidRequestError(f"Unknown planning session '{thread_id}'")

        if values.get("intake_accepted") is False:
            status = PlanStatus.REJECTED
        elif graph_state.interrupts:
            status = PlanStatus.AWAITING_APPROVAL
        else:
            status = PlanStatus.COMPLETED

        sections = {}
        for field_name, heading in RESEARCH_FIELDS.values():
            if values.get(field_name):
                sections[heading] = values[field_name]
        if values.get("budget_results"):
            sections["Budget"] = values["budget_results"]

        return PlanningSnapshot(
            thread_id=thread_id,
            status=status,
            rejection_reason=values.get("rejection_reason", ""),
            supervisor_reasoning=values.get("supervisor_reasoning", ""),
            routing_strategy=values.get("routing_strategy", ""),
            selected_agents=tuple(values.get("selected_agents", [])),
            sections=sections,
            research_failures=tuple(values.get("research_failures", [])),
            budget_verdict=values.get("budget_verdict", ""),
            draft_itinerary=values.get("itinerary", ""),
            revision_count=values.get("revision_count", 0),
            final_plan=values.get("final_response", ""),
            plan_id=values.get("plan_id", ""),
            storage_warning=values.get("storage_warning", ""),
        )

    @staticmethod
    def _config(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}}


def validate_user_id(user_id: str) -> str:
    user_id = (user_id or "").strip()
    if not user_id or len(user_id) > MAX_USER_ID_LENGTH:
        raise InvalidRequestError(f"User ID must be 1-{MAX_USER_ID_LENGTH} characters.")
    return user_id
