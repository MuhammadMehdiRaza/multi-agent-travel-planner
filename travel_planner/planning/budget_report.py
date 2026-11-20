"""Presents a BudgetAssessment and adds LLM money-saving advice.

Kept separate from budget.py on purpose (Single Responsibility): budget.py
calculates, this module formats and explains. Changing the report layout can
never break the calculation.
"""

import logging
from dataclasses import dataclass

from travel_planner.domain.models import TripConstraints
from travel_planner.llm.ports import LLMClient
from travel_planner.planning.budget import BudgetAnalyzer, BudgetAssessment, BudgetVerdict
from travel_planner.planning.money import CurrencyConverter
from travel_planner.planning.research_text import format_research
from travel_planner.shared.exceptions import ExternalServiceError

logger = logging.getLogger(__name__)


# SOLID - SRP: only formats a BudgetAssessment; it never calculates.
class BudgetReportFormatter:
    def __init__(self, converter: CurrencyConverter):
        self._converter = converter

    def to_markdown(self, assessment: BudgetAssessment) -> str:
        estimate = assessment.estimate
        lines = [
            f"**Estimated cost for {assessment.duration_days} days**",
            "",
            "| Category | Estimate |",
            "|---|---|",
        ]
        for category, amount in estimate.items():
            lines.append(f"| {category} | {amount.format()} |")
        lines.append(f"| **Total** | **{estimate.total.format()}** |")
        lines.append("")
        lines.append(self._verdict_text(assessment))

        if assessment.assumptions:
            lines.append("")
            lines.append("_Assumptions: " + " ".join(assessment.assumptions) + "_")
        return "\n".join(lines)

    def _verdict_text(self, assessment: BudgetAssessment) -> str:
        if assessment.verdict is BudgetVerdict.UNKNOWN:
            return "No budget was given, so feasibility could not be checked."

        budget = assessment.budget
        total_in_user_currency = self._converter.convert(assessment.estimate.total, budget.currency)
        label = assessment.verdict.value.replace("_", " ")
        text = (
            f"Your budget: {budget.format()} - estimated total {total_in_user_currency.format()}. "
            f"Verdict: **{label}** (the estimate uses {assessment.usage_ratio:.0%} of the budget)."
        )
        if assessment.verdict is BudgetVerdict.OVER_BUDGET:
            text += f" You are short by about {assessment.shortfall_in_usd.format()}."
        return text


@dataclass(frozen=True)
class BudgetAdvice:
    assessment: BudgetAssessment
    report: str


ADVICE_SYSTEM_PROMPT = "You are a practical travel budget analyst."
ADVICE_PROMPT = """The cost estimate below was calculated by our budget engine. Do not change the numbers.

User request:
{query}

Budget estimate:
{table}

Research collected by other agents:
{research}

Give 3-5 short, specific money-saving suggestions for this trip."""


# SOLID - DIP: receives the analyzer, the formatter and the LLMClient through its constructor.
class BudgetAdvisor:
    def __init__(self, analyzer: BudgetAnalyzer, formatter: BudgetReportFormatter, llm: LLMClient):
        self._analyzer = analyzer
        self._formatter = formatter
        self._llm = llm

    def advise(self, query: str, constraints: TripConstraints, research: dict) -> BudgetAdvice:
        assessment = self._analyzer.assess(constraints)
        table = self._formatter.to_markdown(assessment)
        research_text = format_research(research)

        try:
            tips = self._llm.complete(ADVICE_SYSTEM_PROMPT, ADVICE_PROMPT.format(
                query=query, table=table, research=research_text))
        except ExternalServiceError as error:
            # The calculated numbers are still useful without the AI advice.
            logger.warning("Budget advice unavailable: %s", error)
            tips = "_AI money-saving advice is unavailable right now._"

        return BudgetAdvice(assessment=assessment, report=f"{table}\n\n**Money-saving advice**\n\n{tips}")
