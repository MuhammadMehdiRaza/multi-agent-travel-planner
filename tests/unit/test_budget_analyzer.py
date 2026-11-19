from decimal import Decimal

import pytest

from travel_planner.domain.models import TravelStyle, TripConstraints
from travel_planner.planning.budget import BudgetAnalyzer, BudgetVerdict, classify_budget
from travel_planner.planning.destinations import DEFAULT_PROFILE, DestinationCatalog
from travel_planner.planning.money import Money

from travel_planner.planning.budget_parser import BudgetParser  # noqa: E402
from travel_planner.planning.money import CurrencyConverter  # noqa: E402

analyzer = BudgetAnalyzer(BudgetParser(), CurrencyConverter(), DestinationCatalog())


# ------------------------------------------------------- Boundary Value Analysis on the verdict rule
@pytest.mark.parametrize(
    "ratio, verdict",
    [
        ("0.10", BudgetVerdict.FEASIBLE),
        ("0.85", BudgetVerdict.FEASIBLE),      # boundary: still feasible
        ("0.8501", BudgetVerdict.TIGHT),       # just above
        ("1.00", BudgetVerdict.TIGHT),         # boundary: exactly the budget
        ("1.0001", BudgetVerdict.OVER_BUDGET), # just above
        ("3.5", BudgetVerdict.OVER_BUDGET),
    ],
)
def test_classify_budget_boundaries(ratio, verdict):
    assert classify_budget(Decimal(ratio)) is verdict


# ------------------------------------------------------- cost estimation
def test_tokyo_budget_trip_estimate():
    constraints = TripConstraints(destination="Tokyo", duration_days=7, travel_style=TravelStyle.BUDGET)
    estimate = analyzer.assess(constraints).estimate
    # daily USD 73 x Japan cost index 1.3 x 7 days; flights 950 x 0.9; +10% contingency
    assert estimate.accommodation == Money("318.50", "USD")
    assert estimate.food == Money("182.00", "USD")
    assert estimate.local_transport == Money("72.80", "USD")
    assert estimate.activities == Money("91.00", "USD")
    assert estimate.flights == Money("855.00", "USD")
    assert estimate.contingency == Money("151.93", "USD")
    assert estimate.total == Money("1671.23", "USD")


def test_luxury_costs_more_than_budget_style():
    budget = analyzer.assess(TripConstraints(destination="Paris", duration_days=5, travel_style=TravelStyle.BUDGET))
    luxury = analyzer.assess(TripConstraints(destination="Paris", duration_days=5, travel_style=TravelStyle.LUXURY))
    assert luxury.estimate.total.amount > budget.estimate.total.amount


def test_longer_trip_costs_more():
    short = analyzer.assess(TripConstraints(destination="Dubai", duration_days=3))
    long = analyzer.assess(TripConstraints(destination="Dubai", duration_days=10))
    assert long.estimate.total.amount > short.estimate.total.amount


# ------------------------------------------------------- verdicts
def test_two_lakh_japan_week_is_over_budget():
    assessment = analyzer.assess(
        TripConstraints(destination="Japan", duration_days=7, budget_text="2 lakhs", travel_style=TravelStyle.BUDGET)
    )
    assert assessment.verdict is BudgetVerdict.OVER_BUDGET
    assert assessment.budget == Money(200000, "PKR")
    assert assessment.budget_in_usd == Money("714.29", "USD")
    assert assessment.shortfall_in_usd == Money("956.94", "USD")


def test_generous_budget_is_feasible_with_no_shortfall():
    assessment = analyzer.assess(TripConstraints(destination="Lahore", duration_days=3, budget_text="$2000"))
    assert assessment.verdict is BudgetVerdict.FEASIBLE
    assert assessment.shortfall_in_usd == Money(0, "USD")


def test_missing_budget_gives_unknown_verdict_but_still_estimates():
    assessment = analyzer.assess(TripConstraints(destination="Rome", duration_days=4))
    assert assessment.verdict is BudgetVerdict.UNKNOWN
    assert assessment.budget is None
    assert assessment.usage_ratio is None
    assert assessment.estimate.total.amount > 0


def test_assumptions_are_recorded_for_missing_information():
    assessment = analyzer.assess(TripConstraints(destination="Atlantis"))
    assert assessment.duration_days == 7
    assert any("7 days" in text for text in assessment.assumptions)
    assert any("average" in text for text in assessment.assumptions)


# ------------------------------------------------------- destination catalogue
@pytest.mark.parametrize("destination", ["Tokyo", "Kyoto, Japan", "JAPAN", "New York"])
def test_catalog_finds_known_destinations(destination):
    assert DestinationCatalog().lookup(destination) is not DEFAULT_PROFILE


@pytest.mark.parametrize("destination", ["", "Atlantis", "Newark"])
def test_catalog_falls_back_to_average_profile(destination):
    assert DestinationCatalog().lookup(destination) is DEFAULT_PROFILE


# ------------------------------------------------------- Dependency Inversion: helpers are injected
def test_analyzer_requires_its_helpers_to_be_injected():
    with pytest.raises(TypeError):
        BudgetAnalyzer()  # pylint: disable=no-value-for-parameter


def test_analyzer_uses_the_injected_destination_catalog():
    from travel_planner.planning.destinations import profile  # pylint: disable=import-outside-toplevel

    catalog = DestinationCatalog({"atlantis": profile("1.0", "123")})
    custom = BudgetAnalyzer(BudgetParser(), CurrencyConverter(), catalog)
    estimate = custom.assess(TripConstraints(destination="Atlantis", duration_days=2)).estimate
    assert estimate.flights.amount == Decimal("123")
