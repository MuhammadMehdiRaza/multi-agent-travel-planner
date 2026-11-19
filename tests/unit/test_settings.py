import pytest

from travel_planner.settings import Settings
from travel_planner.shared.exceptions import ConfigurationError

LIVE_ENV = {
    "GROQ_API_KEY": "g",
    "DATA_SOURCE": "live",
    "TAVILY_API_KEY": "t",
    "AVIATION_STACK_API_KEY": "a",
    "OPENWEATHER_API_KEY": "o",
    "DATABASE_URL": "postgresql://localhost/db",
    "AVIATIONSTACK_MCP_PYTHON": "C:/mcp/python.exe",
}


def test_defaults_use_sample_data_mode():
    settings = Settings.from_env({"GROQ_API_KEY": "g"})
    assert settings.data_source == "sample"
    assert settings.groq_model == "openai/gpt-oss-120b"
    assert settings.research_timeout_seconds == 45.0
    assert settings.max_revisions == 2


def test_reads_numeric_values_from_environment():
    settings = Settings.from_env({"GROQ_API_KEY": "g", "RESEARCH_TIMEOUT_SECONDS": "10", "MAX_REVISIONS": "0"})
    assert settings.research_timeout_seconds == 10.0
    assert settings.max_revisions == 0


def test_missing_groq_key_is_a_configuration_error():
    with pytest.raises(ConfigurationError, match="GROQ_API_KEY"):
        Settings.from_env({})


@pytest.mark.parametrize("value", ["cloud", ""])
def test_unknown_data_source_is_rejected(value):
    with pytest.raises(ConfigurationError, match="DATA_SOURCE"):
        Settings.from_env({"GROQ_API_KEY": "g", "DATA_SOURCE": value})


@pytest.mark.parametrize("name, value", [("RESEARCH_TIMEOUT_SECONDS", "0"), ("RESEARCH_TIMEOUT_SECONDS", "abc"),
                                         ("MAX_REVISIONS", "-1"), ("MAX_REVISIONS", "two")])
def test_invalid_numbers_are_rejected(name, value):
    with pytest.raises(ConfigurationError, match=name):
        Settings.from_env({"GROQ_API_KEY": "g", name: value})


def test_live_mode_requires_all_integration_keys():
    env = dict(LIVE_ENV)
    del env["TAVILY_API_KEY"]
    del env["DATABASE_URL"]
    with pytest.raises(ConfigurationError) as excinfo:
        Settings.from_env(env)
    assert "TAVILY_API_KEY" in str(excinfo.value)
    assert "DATABASE_URL" in str(excinfo.value)


def test_complete_live_configuration_is_accepted():
    settings = Settings.from_env(LIVE_ENV)
    assert settings.data_source == "live"
    assert settings.database_url == "postgresql://localhost/db"


def test_aviationstack_key_is_also_read_from_the_name_used_by_the_mcp_server():
    env = {key: value for key, value in LIVE_ENV.items() if key != "AVIATION_STACK_API_KEY"}
    env["AVIATIONSTACK_API_KEY"] = "from-other-name"
    assert Settings.from_env(env).aviation_stack_api_key == "from-other-name"
