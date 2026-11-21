from decimal import Decimal

import pytest

from travel_planner.planning.money import CurrencyConverter, Money
from travel_planner.shared.exceptions import ValidationError


def test_money_accepts_numbers_and_stores_decimal():
    money = Money(1500, "usd")
    assert money.amount == Decimal("1500")
    assert money.currency == "USD"


def test_zero_is_allowed():
    assert Money(0, "PKR").amount == 0


@pytest.mark.parametrize("amount, currency", [(-1, "USD"), (100, "XYZ"), (100, ""),
                                            ("NaN", "USD"), ("Infinity", "USD"), ("bad", "USD")])
def test_invalid_money_is_rejected(amount, currency):
    with pytest.raises(ValidationError):
        Money(amount, currency)


def test_add_same_currency():
    assert Money(10, "USD").add(Money("2.5", "USD")) == Money("12.5", "USD")


def test_add_different_currency_is_rejected():
    with pytest.raises(ValidationError):
        Money(10, "USD").add(Money(10, "PKR"))


def test_multiply():
    assert Money(35, "USD").multiply(Decimal("1.3")) == Money("45.5", "USD")


@pytest.mark.parametrize(
    "money, text",
    [(Money(200000, "PKR"), "PKR 200,000"), (Money("1671.23", "USD"), "USD 1,671"), (Money(0, "EUR"), "EUR 0")],
)
def test_format(money, text):
    assert money.format() == text


converter = CurrencyConverter()


def test_convert_pkr_to_usd():
    assert converter.convert(Money(280000, "PKR"), "USD") == Money("1000.00", "USD")


def test_convert_usd_to_pkr_and_same_currency():
    assert converter.convert(Money(10, "USD"), "PKR") == Money("2800.00", "PKR")
    assert converter.convert(Money(10, "EUR"), "EUR") == Money(10, "EUR")


def test_converter_rejects_unknown_currency():
    with pytest.raises(ValidationError):
        CurrencyConverter({"USD": Decimal(1)}).convert(Money(10, "PKR"), "USD")
