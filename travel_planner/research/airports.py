"""Main airport (IATA code) for common origins and destinations.

AviationStack's airport search needs a paid plan, so the flight agent looks the
code up here and asks AviationStack only for the free flight schedules.
These are planning data (documented assumptions), like the destination profiles.
"""

import re

DEFAULT_ORIGIN_AIRPORT = "LHE"  # travellers are assumed to depart from Pakistan (Lahore)

# Cities come before countries, so "Kyoto, Japan" finds Kyoto's airport, not Tokyo's.
AIRPORT_CODES = {
    # Pakistan
    "lahore": "LHE", "karachi": "KHI", "islamabad": "ISB", "peshawar": "PEW", "multan": "MUX",
    "faisalabad": "LYP", "sialkot": "SKT", "quetta": "UET", "skardu": "KDU", "hunza": "GIL", "gilgit": "GIL",
    # Asia and the Middle East
    "tokyo": "NRT", "kyoto": "KIX", "osaka": "KIX", "beijing": "PEK", "bangkok": "BKK",
    "kuala lumpur": "KUL", "singapore": "SIN", "bali": "DPS", "colombo": "CMB", "male": "MLE",
    "dubai": "DXB", "abu dhabi": "AUH", "doha": "DOH", "makkah": "JED", "jeddah": "JED", "riyadh": "RUH",
    "istanbul": "IST", "cairo": "CAI", "baku": "GYD",
    # Europe
    "london": "LHR", "paris": "CDG", "rome": "FCO", "madrid": "MAD", "berlin": "BER", "zurich": "ZRH",
    # Americas and Oceania
    "new york": "JFK", "toronto": "YYZ", "sydney": "SYD",
    # Countries (main international airport)
    "pakistan": "ISB", "japan": "NRT", "china": "PEK", "thailand": "BKK", "malaysia": "KUL",
    "indonesia": "CGK", "sri lanka": "CMB", "maldives": "MLE", "uae": "DXB", "qatar": "DOH",
    "saudi arabia": "RUH", "turkey": "IST", "egypt": "CAI", "azerbaijan": "GYD", "uk": "LHR",
    "united kingdom": "LHR", "france": "CDG", "italy": "FCO", "spain": "MAD", "germany": "FRA",
    "switzerland": "ZRH", "usa": "JFK", "united states": "JFK", "canada": "YYZ", "australia": "SYD",
}


def find_airport_code(place: str) -> str | None:
    """Return the IATA code of the main airport for a place such as "Kyoto, Japan"; None if unknown."""
    text = (place or "").strip()
    if re.fullmatch(r"[A-Z]{3}", text):  # already an airport code, e.g. "ISB"
        return text
    lowered = text.lower()
    for name, code in AIRPORT_CODES.items():
        if re.search(r"\b" + re.escape(name) + r"\b", lowered):
            return code
    return None
