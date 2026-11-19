"""Turns budget text such as "2 lakhs", "Rs. 150,000" or "$1500" into Money."""

import re
from decimal import Decimal

from travel_planner.planning.money import Money

# A number (with optional commas/decimals) followed by an optional size word.
NUMBER_PATTERN = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakhs?|lacs?|crores?|million)?\b")

MULTIPLIERS = {
    "k": 1_000,
    "thousand": 1_000,
    "lakh": 100_000,
    "lac": 100_000,
    "crore": 10_000_000,
    "million": 1_000_000,
}
SOUTH_ASIAN_UNITS = ("lakh", "lac", "crore")

# Checked in this order. Words are matched at the start of a word ("dollar" matches "dollars").
CURRENCY_MARKERS = [
    ("inr", "INR"), ("indian rupee", "INR"),
    ("pkr", "PKR"), ("rs", "PKR"), ("rupee", "PKR"),
    ("usd", "USD"), ("dollar", "USD"), ("$", "USD"),
    ("eur", "EUR"), ("€", "EUR"),
    ("gbp", "GBP"), ("pound", "GBP"), ("£", "GBP"),
    ("jpy", "JPY"), ("yen", "JPY"), ("¥", "JPY"),
    ("aed", "AED"), ("dirham", "AED"),
    ("sar", "SAR"), ("riyal", "SAR"),
]


class BudgetParser:
    def __init__(self, default_currency: str = "PKR"):
        self._default_currency = default_currency

    def parse(self, text) -> Money | None:
        """Return the budget as Money, or None if no positive amount is found."""
        if not text:
            return None
        lowered = str(text).lower()

        match = NUMBER_PATTERN.search(lowered)
        if match is None:
            return None

        amount = Decimal(match.group(1).replace(",", ""))
        unit = match.group(2)
        if unit:
            unit = unit.rstrip("s")  # "lakhs" -> "lakh"
            amount = amount * MULTIPLIERS[unit]

        if amount <= 0:
            return None
        return Money(amount, self._find_currency(lowered, unit))

    def _find_currency(self, lowered: str, unit: str | None) -> str:
        for marker, currency in CURRENCY_MARKERS:
            if marker.isalpha() or " " in marker:
                found = re.search(r"\b" + marker, lowered) is not None
            else:
                found = marker in lowered  # currency symbols such as $ or €
            if found:
                return currency
        if unit in SOUTH_ASIAN_UNITS:
            return "PKR"  # lakh / crore amounts are rupees
        return self._default_currency
