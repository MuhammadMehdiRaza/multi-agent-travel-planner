from decimal import Decimal

import pytest

from travel_planner.planning.budget_parser import BudgetParser
from travel_planner.planning.money import Money

parser = BudgetParser()


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2 lakhs", Money(200000, "PKR")),
        ("Rs. 2 lakh", Money(200000, "PKR")),
        ("1.5 lac", Money(150000, "PKR")),
        ("PKR 150,000", Money(150000, "PKR")),
        ("2,00,000 rupees", Money(200000, "PKR")),
        ("1 crore", Money(10000000, "PKR")),
        ("$1500", Money(1500, "USD")),
        ("1,200 USD", Money(1200, "USD")),
        ("2k dollars", Money(2000, "USD")),
        ("€800", Money(800, "EUR")),
        ("900 euros", Money(900, "EUR")),
        ("£2,000", Money(2000, "GBP")),
        ("300000 yen", Money(300000, "JPY")),
        ("5000 AED", Money(5000, "AED")),
        ("50000 INR", Money(50000, "INR")),
        ("1.2 million", Money(1200000, "PKR")),
        ("150000", Money(150000, "PKR")),  # no currency -> default currency
    ],
)
def test_parses_budget_formats(text, expected):
    assert parser.parse(text) == expected


@pytest.mark.parametrize("text", ["", None, "flexible", "two lakh", "0", "Rs 0"])
def test_returns_none_when_no_positive_amount(text):
    assert parser.parse(text) is None


def test_default_currency_is_configurable():
    assert BudgetParser(default_currency="USD").parse("2500") == Money(Decimal(2500), "USD")


def test_does_not_mistake_words_containing_rs_for_rupees():
    assert BudgetParser(default_currency="USD").parse("3000 for hours of fun") == Money(3000, "USD")
