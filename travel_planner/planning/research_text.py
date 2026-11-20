"""Turns the research sections into prompt text of a bounded size.

The research agents can return long answers. Sending all of it again to the budget
and itinerary prompts made those requests larger than Groq's free-tier limit
(8,000 tokens per minute), so each section is shortened first.
"""

MAX_CHARS_PER_SECTION = 1500
SHORTENED_MARK = " ...[shortened]"


def format_research(research: dict, max_chars_per_section: int = MAX_CHARS_PER_SECTION) -> str:
    """Join the research sections, cutting each one to at most max_chars_per_section characters."""
    parts = []
    for name, text in research.items():
        text = str(text)
        if len(text) > max_chars_per_section:
            text = text[:max_chars_per_section] + SHORTENED_MARK
        parts.append(f"{name}:\n{text}")
    return "\n\n".join(parts) or "none"
