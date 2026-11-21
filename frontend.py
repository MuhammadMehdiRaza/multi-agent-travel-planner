"""Streamlit user interface.

Run with:  streamlit run frontend.py

The page only talks to TravelPlanningFacade (start_planning, submit_decision,
history). It knows nothing about LangGraph, MCP or the database.
"""

import logging

import streamlit as st

from travel_planner.bootstrap import build_facade
from travel_planner.shared.exceptions import ConfigurationError, TravelPlannerError
from travel_planner.workflow.facade import PlanStatus

logger = logging.getLogger("travel_planner.ui")

VERDICT_STYLE = {
    "FEASIBLE": st.success,
    "TIGHT": st.warning,
    "OVER_BUDGET": st.error,
    "UNKNOWN": st.info,
}


@st.cache_resource
def get_facade():
    """Created once and shared by all browser sessions (the facade is thread-safe)."""
    return build_facade()


def run_action(action, spinner_text: str) -> None:
    """Run a facade call and show errors to the user instead of a stack trace."""
    try:
        with st.spinner(spinner_text):
            st.session_state.snapshot = action()
    except TravelPlannerError as error:
        # The full technical message goes to the log; the user sees a safe, plain message.
        logger.warning("Request failed: %s", error)
        st.error(error.user_message)
    except Exception:  # pylint: disable=broad-exception-caught
        # Last line of defence at the UI boundary: log the details, show a friendly message.
        logger.exception("Unexpected error in the user interface")
        st.error("Something went wrong. Please try again.")


def show_markdown(text: str) -> None:
    """Show AI-written text. '$' is escaped, otherwise Streamlit reads 'US $5 ... $7' as a math formula."""
    st.markdown(text.replace("$", "\\$"))


def show_history(facade, user_id: str) -> None:
    st.subheader("My saved plans")
    try:
        records = facade.history(user_id, limit=5)
    except TravelPlannerError as error:
        logger.warning("History unavailable: %s", error)
        st.caption(f"History unavailable: {error.user_message}")
        return
    if not records:
        st.caption("No saved plans yet.")
    for record in records:
        # Times are stored in UTC; show them in the computer's local time zone.
        title = f"{record.destination or 'Trip'} - {record.created_at.astimezone():%d %b %Y %H:%M}"
        with st.expander(title):
            show_markdown(record.final_plan)


def show_snapshot(facade, snapshot) -> None:
    if snapshot.status is PlanStatus.REJECTED:
        st.warning(f"Request not accepted: {snapshot.rejection_reason}")
        return

    st.subheader("Supervisor plan")
    st.write(snapshot.supervisor_reasoning)
    st.caption(f"Agents: {', '.join(snapshot.selected_agents)} | routing: {snapshot.routing_strategy}")
    if snapshot.research_failures:
        st.warning("Some research could not be completed: " + ", ".join(snapshot.research_failures))

    left, right = st.columns(2)
    for index, (heading, text) in enumerate(snapshot.sections.items()):
        # sections alternate between the left and the right column
        if index % 2 == 0:
            column = left
        else:
            column = right
        with column:
            st.subheader(heading)
            if heading == "Budget" and snapshot.budget_verdict in VERDICT_STYLE:
                verdict_text = snapshot.budget_verdict.replace('_', ' ')
                VERDICT_STYLE[snapshot.budget_verdict](f"Budget verdict: {verdict_text}")
            show_markdown(text)

    st.subheader(f"Draft itinerary (revision {snapshot.revision_count})")
    show_markdown(snapshot.draft_itinerary)

    if snapshot.status is PlanStatus.AWAITING_APPROVAL:
        st.divider()
        st.subheader("Your approval")
        choice = st.radio("Approve this draft?", ["Yes", "No, revise it"], horizontal=True)
        feedback = st.text_area("What should change?", disabled=choice == "Yes")
        if st.button("Submit decision"):
            run_action(
                lambda: facade.submit_decision(snapshot.thread_id, choice == "Yes", feedback),
                "Updating your plan...",
            )
            st.rerun()

    if snapshot.status is PlanStatus.COMPLETED:
        st.divider()
        st.subheader("Final travel plan")
        if snapshot.storage_warning:
            st.warning(snapshot.storage_warning)
        show_markdown(snapshot.final_plan)


def main() -> None:
    st.set_page_config(page_title="Multi-Agent Travel Planner", layout="wide")
    st.title("Multi-Agent Travel Planner")

    try:
        facade = get_facade()
    except ConfigurationError as error:
        st.error(f"Configuration problem: {error}")
        st.stop()

    with st.sidebar:
        user_id = st.text_input("User ID", value="demo_user")
        if st.button("Start a new plan"):
            st.session_state.pop("snapshot", None)
        show_history(facade, user_id)

    query = st.text_area(
        "Travel request",
        placeholder=(
            "Plan a 7-day Japan trip under Rs. 2 lakh. I prefer budget hotels and no overnight flights."
        ),
        height=110,
    )
    if st.button("Create draft plan", type="primary"):
        run_action(lambda: facade.start_planning(user_id, query), "Agents are planning...")

    snapshot = st.session_state.get("snapshot")
    if snapshot is not None:
        show_snapshot(facade, snapshot)


main()
