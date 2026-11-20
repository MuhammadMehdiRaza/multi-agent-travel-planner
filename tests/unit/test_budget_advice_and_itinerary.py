from travel_planner.domain.models import TravelStyle, TripConstraints
from travel_planner.planning.budget import BudgetAnalyzer
from travel_planner.planning.budget_parser import BudgetParser
from travel_planner.planning.destinations import DestinationCatalog
from travel_planner.planning.money import CurrencyConverter
from travel_planner.planning.budget_report import BudgetAdvisor, BudgetReportFormatter
from travel_planner.planning.itinerary import FinalPlanComposer, ItineraryPlanner
from travel_planner.shared.exceptions import ExternalServiceError
from tests.fakes import ScriptedLLMClient

def analyzer():
    return BudgetAnalyzer(BudgetParser(), CurrencyConverter(), DestinationCatalog())


def formatter():
    return BudgetReportFormatter(CurrencyConverter())


JAPAN = TripConstraints(destination="Japan", duration_days=7, budget_text="2 lakhs", travel_style=TravelStyle.BUDGET)


def test_report_shows_categories_totals_and_verdict():
    report = formatter().to_markdown(analyzer().assess(JAPAN))
    for text in ["Flights", "Accommodation", "Contingency", "USD 1,671", "PKR 200,000", "OVER BUDGET"]:
        assert text in report


def test_report_for_unknown_budget_says_so():
    report = formatter().to_markdown(analyzer().assess(TripConstraints(destination="Rome")))
    assert "No budget was given" in report


def test_advisor_combines_numbers_with_llm_advice():
    llm = ScriptedLLMClient(["Travel in the off-season."])
    advice = BudgetAdvisor(analyzer(), formatter(), llm).advise("Japan trip", JAPAN, {"Flight": "PIA"})
    assert advice.assessment.verdict.value == "OVER_BUDGET"
    assert "Travel in the off-season." in advice.report
    assert "USD 1,671" in llm.prompts[0][1]  # the LLM is given the calculated numbers


def test_advisor_still_returns_numbers_when_llm_fails():
    class DownLLM(ScriptedLLMClient):
        def complete(self, system_prompt, user_prompt):
            raise ExternalServiceError("groq", "rate limited")

    advice = BudgetAdvisor(analyzer(), formatter(), DownLLM()).advise("q", JAPAN, {})
    assert "USD 1,671" in advice.report
    assert "unavailable" in advice.report


def test_itinerary_prompt_contains_research_budget_and_feedback():
    llm = ScriptedLLMClient(["Day 1: Tokyo"])
    draft = ItineraryPlanner(llm).draft(
        "Japan trip", JAPAN, {"Flight": "Fly PIA", "Weather": "Mild"}, "Budget table", feedback="Add Kyoto"
    )
    assert draft == "Day 1: Tokyo"
    prompt = llm.prompts[0][1]
    for text in ["Fly PIA", "Mild", "Budget table", "Add Kyoto", "7"]:
        assert text in prompt


def test_itinerary_prompt_without_feedback_has_no_revision_section():
    llm = ScriptedLLMClient(["plan"])
    ItineraryPlanner(llm).draft("q", JAPAN, {}, "")
    assert "Reviewer feedback" not in llm.prompts[0][1]


def test_final_plan_uses_approval_or_feedback():
    llm = ScriptedLLMClient(["approved plan", "revised plan"])
    composer = FinalPlanComposer(llm)
    assert composer.compose("q", "draft", "budget", approved=True, feedback="") == "approved plan"
    assert composer.compose("q", "draft", "budget", approved=False, feedback="cheaper hotels") == "revised plan"
    assert "approved" in llm.prompts[0][1].lower()
    assert "cheaper hotels" in llm.prompts[1][1]


def test_itinerary_prompt_keeps_the_budget_currency_and_verdict():
    llm = ScriptedLLMClient(["plan"])
    ItineraryPlanner(llm).draft("q", JAPAN, {}, "Verdict: **OVER BUDGET**")
    prompt = llm.prompts[0][1]
    assert "Never use Indian rupees" in prompt
    assert "verdict" in prompt and "is final" in prompt
    assert "Pakistan" in prompt  # default origin when none is given


def test_final_plan_prompt_keeps_the_budget_currency_and_verdict():
    llm = ScriptedLLMClient(["plan"])
    FinalPlanComposer(llm).compose("q", "draft", "budget", approved=True, feedback="")
    prompt = llm.prompts[0][1]
    assert "Never use Indian rupees" in prompt and "is final" in prompt
    assert "never calculate a different total" in prompt


def test_long_research_is_shortened_before_it_is_sent_to_the_llm():
    llm = ScriptedLLMClient(["plan", "tips"])
    research = {"Flights": "x" * 10_000, "Hotels": "y" * 10_000}
    ItineraryPlanner(llm).draft("q", JAPAN, research, "budget")
    BudgetAdvisor(analyzer(), formatter(), llm).advise("q", JAPAN, research)
    for _, prompt in llm.prompts:
        assert len(prompt) < 6_000
        assert "[shortened]" in prompt
