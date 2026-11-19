"""Money value object and currency conversion.

Decimal is used instead of float because floats cannot store values like 0.1
exactly, which causes rounding errors in money calculations.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from travel_planner.shared.exceptions import ValidationError

CENTS = Decimal("0.01")

# Approximate units of each currency per 1 US dollar (October 2026).
# Static on purpose: estimates must be reproducible in tests. Update when needed.
DEFAULT_RATES_PER_USD = {
    "USD": Decimal("1"),
    "PKR": Decimal("280"),
    "EUR": Decimal("0.92"),
    "GBP": Decimal("0.79"),
    "JPY": Decimal("150"),
    "AED": Decimal("3.67"),
    "SAR": Decimal("3.75"),
    "INR": Decimal("84"),
}
SUPPORTED_CURRENCIES = tuple(DEFAULT_RATES_PER_USD)


@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self):
        # Accept int/str/float for convenience but always store a Decimal and an upper-case code.
        object.__setattr__(self, "amount", Decimal(str(self.amount)))
        object.__setattr__(self, "currency", str(self.currency).upper())
        if self.amount < 0:
            raise ValidationError(f"Money cannot be negative: {self.amount}")
        if self.currency not in SUPPORTED_CURRENCIES:
            raise ValidationError(f"Unsupported currency '{self.currency}'")

    def add(self, other: "Money") -> "Money":
        if other.currency != self.currency:
            raise ValidationError(f"Cannot add {other.currency} to {self.currency}")
        return Money(self.amount + other.amount, self.currency)

    def multiply(self, factor) -> "Money":
        return Money(self.amount * Decimal(str(factor)), self.currency)

    def rounded(self) -> "Money":
        return Money(self.amount.quantize(CENTS, rounding=ROUND_HALF_UP), self.currency)

    def format(self) -> str:
        """Whole units with thousands separators, e.g. 'PKR 200,000'."""
        return f"{self.currency} {self.amount:,.0f}"


class CurrencyConverter:
    def __init__(self, rates_per_usd: dict | None = None):
        self._rates = rates_per_usd or DEFAULT_RATES_PER_USD

    def convert(self, money: Money, target_currency: str) -> Money:
        target_currency = target_currency.upper()
        if money.currency == target_currency:
            return money
        if money.currency not in self._rates or target_currency not in self._rates:
            raise ValidationError(f"No exchange rate for {money.currency} -> {target_currency}")

        in_usd = money.amount / self._rates[money.currency]
        return Money(in_usd * self._rates[target_currency], target_currency).rounded()
