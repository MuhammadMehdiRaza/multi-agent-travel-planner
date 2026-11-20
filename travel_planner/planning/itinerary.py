"""LLM agents that write the draft itinerary and the final plan."""

from travel_planner.domain.models import TripConstraints
from travel_planner.llm.ports import LLMClient
from travel_planner.planning.research_text import format_research

# Rules shared by the draft and the final plan. Our users are in Pakistan, and the budget
# verdict comes from the deterministic budget engine, so the LLM must not contradict it.
PLAN_RULES = """Rules:
- Show every price in the currency of the traveller's budget shown in the budget analysis
  (Pakistani rupees, PKR, if no budget is given). Never use Indian rupees.
- The budget verdict in the budget analysis is final. If it says OVER BUDGET or TIGHT, say so
  clearly and suggest where to save; never claim that the plan fits the budget.
- Use the estimated total from the budget analysis; never calculate a different total.
- If no departure city is given, assume the traveller starts from Pakistan (Lahore, Karachi or Islamabad)."""

ITINERARY_SYSTEM_PROMPT = "You are an expert itinerary planner."
ITINERARY_PROMPT = """Create a clear day-by-day draft travel itinerary.

User request:
{query}

Destination: {destination}
Trip length: {days}
Travel style: {style}
Special preferences: {preferences}

Research:
{research}

Budget analysis:
{budget}
{feedback_section}
{rules}

Make the output structured, practical and ready for human review."""

FEEDBACK_SECTION = """
Reviewer feedback on the previous draft (you MUST address it):
{feedback}
"""


# SOLID - SRP: ItineraryPlanner only drafts; FinalPlanComposer writes the final plan.
# SOLID - DIP: both receive the LLMClient abstraction through the constructor.
class ItineraryPlanner:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def draft(self, query: str, constraints: TripConstraints, research: dict, budget_report: str,
              feedback: str = "") -> str:
        feedback_section = FEEDBACK_SECTION.format(feedback=feedback) if feedback else ""
        days = f"{constraints.duration_days} days" if constraints.duration_days else "not specified"

        prompt = ITINERARY_PROMPT.format(
            query=query,
            destination=constraints.destination or "not specified",
            days=days,
            style=constraints.travel_style.value,
            preferences=", ".join(constraints.special_preferences) or "none",
            research=format_research(research),
            budget=budget_report or "not requested",
            feedback_section=feedback_section,
            rules=PLAN_RULES,
        )
        return self._llm.complete(ITINERARY_SYSTEM_PROMPT, prompt)


FINAL_SYSTEM_PROMPT = "You produce final, user-ready travel plans."
APPROVED_PROMPT = """The human reviewer approved this draft itinerary.
Produce the final polished travel plan.

Original request:
{query}

Draft itinerary:
{itinerary}

Budget notes:
{budget}

{rules}"""

NOT_APPROVED_PROMPT = """The human reviewer did not fully approve the draft.
Produce the final travel plan and make sure the reviewer's feedback is applied.

Original request:
{query}

Draft itinerary:
{itinerary}

Reviewer feedback:
{feedback}

Budget notes:
{budget}

{rules}"""


class FinalPlanComposer:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def compose(self, query: str, itinerary: str, budget_report: str, approved: bool, feedback: str) -> str:
        budget = budget_report or "not requested"
        if approved:
            prompt = APPROVED_PROMPT.format(query=query, itinerary=itinerary, budget=budget, rules=PLAN_RULES)
        else:
            prompt = NOT_APPROVED_PROMPT.format(
                query=query, itinerary=itinerary, feedback=feedback, budget=budget, rules=PLAN_RULES
            )
        return self._llm.complete(FINAL_SYSTEM_PROMPT, prompt)
