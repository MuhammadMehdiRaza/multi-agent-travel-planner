"""Deterministic budget analysis: estimate trip cost and compare it with the user's budget.

The prototype asked the LLM to "guess" whether a plan fits the budget, which
gave different answers each time and could not be tested. The numbers are now
calculated by plain code; the LLM is only used afterwards to give advice.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

from travel_planner.domain.models import TravelStyle, TripConstraints
from travel_planner.planning.budget_parser import BudgetParser
from travel_planner.planning.destinations import DEFAULT_PROFILE, DestinationCatalog, DestinationProfile
from travel_planner.planning.money import CurrencyConverter, Money

DEFAULT_DURATION_DAYS = 7
CONTINGENCY_RATE = Decimal("0.10")  # 10% safety margin for unexpected costs
FEASIBLE_LIMIT = Decimal("0.85")    # estimate uses at most 85% of the budget
TIGHT_LIMIT = Decimal("1.00")       # estimate uses at most 100% of the budget

# Daily costs in USD for an average destination (cost_index = 1.0).
DAILY_COSTS_USD = {
    TravelStyle.BUDGET: {"accommodation": 35, "food": 20, "local_transport": 8, "activities": 10},
    TravelStyle.MID_RANGE: {"accommodation": 90, "food": 40, "local_transport": 15, "activities": 25},
    TravelStyle.LUXURY: {"accommodation": 250, "food": 90, "local_transport": 40, "activities": 70},
}
# Budget travellers find cheaper fares; luxury travellers usually fly business class.
FLIGHT_FARE_FACTOR = {
    TravelStyle.BUDGET: Decimal("0.9"),
    TravelStyle.MID_RANGE: Decimal("1.0"),
    TravelStyle.LUXURY: Decimal("2.5"),
}


class BudgetVerdict(str, Enum):
    FEASIBLE = "FEASIBLE"
    TIGHT = "TIGHT"
    OVER_BUDGET = "OVER_BUDGET"
    UNKNOWN = "UNKNOWN"  # the user gave no budget


def classify_budget(usage_ratio: Decimal) -> BudgetVerdict:
    """usage_ratio = estimated cost / budget."""
    if usage_ratio <= FEASIBLE_LIMIT:
        return BudgetVerdict.FEASIBLE
    if usage_ratio <= TIGHT_LIMIT:
        return BudgetVerdict.TIGHT
    return BudgetVerdict.OVER_BUDGET


@dataclass(frozen=True)
class CostBreakdown:
    """Estimated trip cost per category, in USD."""

    flights: Money
    accommodation: Money
    food: Money
    local_transport: Money
    activities: Money
    contingency: Money

    @property
    def total(self) -> Money:
        total = Money(0, "USD")
        for _category, amount in self.items():
            total = total.add(amount)
        return total

    def items(self) -> list[tuple[str, Money]]:
        return [
            ("Flights", self.flights),
            ("Accommodation", self.accommodation),
            ("Food", self.food),
            ("Local transport", self.local_transport),
            ("Activities", self.activities),
            ("Contingency (10%)", self.contingency),
        ]


@dataclass(frozen=True)
class BudgetAssessment:
    verdict: BudgetVerdict
    estimate: CostBreakdown
    duration_days: int
    budget: Money | None = None          # in the user's own currency
    budget_in_usd: Money | None = None
    usage_ratio: Decimal | None = None
    assumptions: tuple[str, ...] = ()

    @property
    def shortfall_in_usd(self) -> Money:
        """How much more money is needed (0 if the budget is enough or unknown)."""
        if self.budget_in_usd is None:
            return Money(0, "USD")
        missing = self.estimate.total.amount - self.budget_in_usd.amount
        return Money(max(missing, Decimal(0)), "USD")


# SOLID - SRP: BudgetAnalyzer only calculates; BudgetReportFormatter presents the result.
# SOLID - DIP: the parser, converter and catalog are injected by the composition root (bootstrap.py).
class BudgetAnalyzer:
    def __init__(self, parser: BudgetParser, converter: CurrencyConverter, catalog: DestinationCatalog):
        self._parser = parser
        self._converter = converter
        self._catalog = catalog

    def assess(self, constraints: TripConstraints) -> BudgetAssessment:
        assumptions = []

        days = constraints.duration_days
        if days is None:
            days = DEFAULT_DURATION_DAYS
            assumptions.append(f"Trip length was not given, so {DEFAULT_DURATION_DAYS} days were assumed.")

        destination = self._catalog.lookup(constraints.destination)
        if destination is DEFAULT_PROFILE:
            assumptions.append("Destination is not in the cost table, so average prices were assumed.")

        estimate = self.estimate_costs(days, constraints.travel_style, destination)

        budget = self._parser.parse(constraints.budget_text)
        if budget is None:
            return BudgetAssessment(BudgetVerdict.UNKNOWN, estimate, days, assumptions=tuple(assumptions))

        budget_in_usd = self._converter.convert(budget, "USD")
        if budget_in_usd.amount == 0:  # e.g. a tiny JPY amount rounds to 0.00 USD
            usage_ratio = Decimal("Infinity")
        else:
            usage_ratio = estimate.total.amount / budget_in_usd.amount

        return BudgetAssessment(
            verdict=classify_budget(usage_ratio),
            estimate=estimate,
            duration_days=days,
            budget=budget,
            budget_in_usd=budget_in_usd,
            usage_ratio=usage_ratio,
            assumptions=tuple(assumptions),
        )

    @staticmethod
    def estimate_costs(days: int, style: TravelStyle, destination: DestinationProfile) -> CostBreakdown:
        daily = DAILY_COSTS_USD[style]

        def for_whole_trip(category: str) -> Money:
            return Money(daily[category], "USD").multiply(destination.cost_index * days).rounded()

        flights = Money(destination.round_trip_fare_usd, "USD").multiply(FLIGHT_FARE_FACTOR[style]).rounded()
        accommodation = for_whole_trip("accommodation")
        food = for_whole_trip("food")
        local_transport = for_whole_trip("local_transport")
        activities = for_whole_trip("activities")

        subtotal = flights.add(accommodation).add(food).add(local_transport).add(activities)
        contingency = subtotal.multiply(CONTINGENCY_RATE).rounded()
        return CostBreakdown(flights, accommodation, food, local_transport, activities, contingency)
