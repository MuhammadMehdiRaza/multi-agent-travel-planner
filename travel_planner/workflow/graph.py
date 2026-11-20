"""Builds the LangGraph workflow.

    START -> intake --(rejected)--> END
               |
               v
            research  (flight / hotel / weather in parallel)
               |
               +--(budget selected)--> budget --+
               |                                |
               v                                v
            draft_itinerary <-------------------+
               |          ^
               v          | (rejected, revisions left)
            human_approval (pauses for the user)
               |
               v (approved, or revision limit reached)
            finalize -> END
"""

from langgraph.graph import END, START, StateGraph

from travel_planner.workflow.nodes import (
    PlanningNodes,
    route_after_approval,
    route_after_intake,
    route_after_research,
)
from travel_planner.workflow.state import TravelState


def build_planning_graph(nodes: PlanningNodes, checkpointer):
    """A checkpointer is REQUIRED: interrupt() needs it to pause and resume.

    (The prototype compiled the graph without one when DATABASE_URL was missing,
    so the human-approval step crashed.)
    """
    graph = StateGraph(TravelState)

    graph.add_node("intake", nodes.intake)
    graph.add_node("research", nodes.research)
    graph.add_node("budget", nodes.budget)
    graph.add_node("draft_itinerary", nodes.draft_itinerary)
    graph.add_node("human_approval", nodes.human_approval)
    graph.add_node("finalize", nodes.finalize)

    graph.add_edge(START, "intake")
    graph.add_conditional_edges("intake", route_after_intake, {"research": "research", "rejected": END})
    graph.add_conditional_edges(
        "research", route_after_research, {"budget": "budget", "draft_itinerary": "draft_itinerary"}
    )
    graph.add_edge("budget", "draft_itinerary")
    graph.add_edge("draft_itinerary", "human_approval")
    graph.add_conditional_edges(
        "human_approval", route_after_approval, {"draft_itinerary": "draft_itinerary", "finalize": "finalize"}
    )
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=checkpointer)
