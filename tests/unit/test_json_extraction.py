import pytest

from travel_planner.shared.exceptions import LLMResponseFormatError
from travel_planner.shared.json_extraction import extract_json_object


def test_extracts_plain_json_object():
    assert extract_json_object('{"allowed": true, "reason": ""}') == {"allowed": True, "reason": ""}


def test_extracts_object_surrounded_by_prose():
    text = 'Sure! Here is the result:\n{"allowed": false, "reason": "off topic"}\nHope this helps.'
    assert extract_json_object(text) == {"allowed": False, "reason": "off topic"}


def test_extracts_object_inside_markdown_code_fence():
    text = '```json\n{"selected_agents": ["flight_agent"]}\n```'
    assert extract_json_object(text) == {"selected_agents": ["flight_agent"]}


def test_skips_braces_that_are_not_valid_json():
    text = 'Use {placeholder} syntax. Result: {"ok": 1}'
    assert extract_json_object(text) == {"ok": 1}


def test_nested_objects_are_preserved():
    text = '{"trip_constraints": {"destination": "Japan", "special_preferences": []}}'
    assert extract_json_object(text)["trip_constraints"]["destination"] == "Japan"


@pytest.mark.parametrize("text", ["", "no json here", "[1, 2, 3]", "{broken: json"])
def test_raises_format_error_when_no_object_present(text):
    with pytest.raises(LLMResponseFormatError) as excinfo:
        extract_json_object(text)
    assert excinfo.value.raw_response == text


def test_rejects_non_string_input():
    with pytest.raises(LLMResponseFormatError):
        extract_json_object(None)  # type: ignore[arg-type]
