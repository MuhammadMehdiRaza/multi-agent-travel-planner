"""The data passed between LangGraph nodes.

Only plain values (str, int, bool, list, dict) are stored here because
LangGraph saves this state in the checkpoint database while the workflow is
paused for human approval. Nodes convert it to domain objects when needed.
"""

from typing import TypedDict


class TravelState(TypedDict, total=False):
    # request
    thread_id: str
    user_id: str
    user_query: str

    # Module 1 - intake
    intake_accepted: bool
    rejection_reason: str
    selected_agents: list[str]
    routing_strategy: str
    supervisor_reasoning: str
    trip_constraints: dict

    # Module 2 - research
    flight_results: str
    hotel_results: str
    weather_results: str
    research_failures: list[str]

    # Module 3 - planning
    budget_results: str
    budget_verdict: str
    itinerary: str

    # Module 4 - approval and result
    revision_count: int
    approved: bool
    human_feedback: str
    next_step: str
    final_response: str
    plan_id: str
    storage_warning: str
