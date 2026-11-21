"""Price level and typical return airfare for common destinations.

cost_index : daily cost compared with an average destination (1.0 = average)
fare_usd   : typical economy return fare from Pakistan in USD

These are planning estimates (documented assumptions), not live prices.
"""

import re
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class DestinationProfile:
    cost_index: Decimal
    round_trip_fare_usd: Decimal


def profile(cost_index: str, fare_usd: str) -> DestinationProfile:
    return DestinationProfile(Decimal(cost_index), Decimal(fare_usd))


DEFAULT_PROFILE = profile("1.0", "700")

DESTINATION_PROFILES = {
    # Pakistan (domestic)
    "pakistan": profile("0.35", "120"), "lahore": profile("0.35", "120"), "karachi": profile("0.35", "120"),
    "islamabad": profile("0.35", "120"), "hunza": profile("0.4", "150"), "skardu": profile("0.4", "180"),
    "murree": profile("0.35", "60"), "swat": profile("0.35", "80"),
    # Asia & Middle East
    "japan": profile("1.3", "950"), "tokyo": profile("1.3", "950"), "kyoto": profile("1.3", "950"),
    "osaka": profile("1.3", "950"), "china": profile("0.9", "700"), "thailand": profile("0.6", "450"),
    "bangkok": profile("0.6", "450"), "malaysia": profile("0.6", "500"),
    "kuala lumpur": profile("0.6", "500"),
    "singapore": profile("1.3", "550"), "indonesia": profile("0.6", "650"), "bali": profile("0.6", "650"),
    "sri lanka": profile("0.5", "400"), "maldives": profile("1.6", "600"), "dubai": profile("1.1", "350"),
    "uae": profile("1.1", "350"), "saudi arabia": profile("0.9", "550"), "makkah": profile("0.9", "550"),
    "turkey": profile("0.7", "600"), "istanbul": profile("0.7", "600"), "egypt": profile("0.6", "650"),
    # Europe
    "uk": profile("1.5", "1000"), "london": profile("1.5", "1000"), "france": profile("1.4", "900"),
    "paris": profile("1.4", "900"), "italy": profile("1.3", "900"), "rome": profile("1.3", "900"),
    "spain": profile("1.2", "900"), "germany": profile("1.3", "850"), "switzerland": profile("1.7", "950"),
    # Americas & Oceania
    "usa": profile("1.6", "1400"), "new york": profile("1.7", "1400"), "canada": profile("1.4", "1300"),
    "australia": profile("1.4", "1400"),
}


class DestinationCatalog:
    def __init__(self, profiles: dict | None = None):
        self._profiles = profiles or DESTINATION_PROFILES

    def lookup(self, destination: str) -> DestinationProfile:
        """Find the profile for a destination such as "Kyoto, Japan"; average profile if unknown."""
        lowered = (destination or "").lower()
        for name, destination_profile in self._profiles.items():
            if re.search(r"\b" + re.escape(name) + r"\b", lowered):
                return destination_profile
        return DEFAULT_PROFILE
