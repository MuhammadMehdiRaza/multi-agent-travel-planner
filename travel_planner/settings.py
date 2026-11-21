"""Application settings, read once from environment variables and validated.

The prototype read environment variables at import time and hard-coded
absolute paths such as ``E:\\Multi_agent_system_with_MCP\\...``, so it only ran on
one laptop. All machine-specific values now come from the environment (.env),
and invalid configuration fails fast with a clear ConfigurationError.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from travel_planner.shared.exceptions import ConfigurationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_SOURCES = ("live", "sample")
# Default Groq model (Llama 3.3 70B was retired by Groq in 2026). Change it with GROQ_MODEL in .env.
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


@dataclass(frozen=True)
class Settings:
    # Security (QR-04): repr=False keeps the secret fields out of printed or logged settings.
    groq_api_key: str = field(repr=False)
    groq_model: str
    # "live"   = real MCP servers + PostgreSQL
    # "sample" = built-in sample data + SQLite (only the LLM is reached over the internet)
    data_source: str
    tavily_api_key: str = field(repr=False)
    aviation_stack_api_key: str = field(repr=False)
    openweather_api_key: str = field(repr=False)
    database_url: str = field(repr=False)
    aviationstack_mcp_python: str
    weather_mcp_python: str
    weather_mcp_script: str
    sqlite_path: str
    research_timeout_seconds: float
    max_revisions: int

    @classmethod
    def from_env(cls, env=None) -> "Settings":
        """Create settings from a dict of environment variables (default: os.environ)."""
        if env is None:
            env = os.environ

        # The AviationStack MCP server accepts both names, so both are accepted here too.
        aviation_key = _read(env, "AVIATION_STACK_API_KEY") or _read(env, "AVIATIONSTACK_API_KEY")

        settings = cls(
            groq_api_key=_read(env, "GROQ_API_KEY"),
            groq_model=_read(env, "GROQ_MODEL", DEFAULT_GROQ_MODEL),
            data_source=_read(env, "DATA_SOURCE", "sample").lower(),
            tavily_api_key=_read(env, "TAVILY_API_KEY"),
            aviation_stack_api_key=aviation_key,
            openweather_api_key=_read(env, "OPENWEATHER_API_KEY"),
            database_url=_read(env, "DATABASE_URL"),
            aviationstack_mcp_python=_read(env, "AVIATIONSTACK_MCP_PYTHON"),
            weather_mcp_python=_read(env, "WEATHER_MCP_PYTHON", sys.executable),
            weather_mcp_script=_read(env, "WEATHER_MCP_SCRIPT", str(PROJECT_ROOT / "weather_mcp_server.py")),
            sqlite_path=_read(env, "SQLITE_PATH", str(PROJECT_ROOT / "data" / "trip_plans.sqlite3")),
            research_timeout_seconds=_positive_float(
                _read(env, "RESEARCH_TIMEOUT_SECONDS", "45"), "RESEARCH_TIMEOUT_SECONDS"),
            max_revisions=_non_negative_int(_read(env, "MAX_REVISIONS", "2"), "MAX_REVISIONS"),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.groq_api_key:
            raise ConfigurationError("GROQ_API_KEY must be set (get a free key at https://console.groq.com)")
        if self.data_source not in DATA_SOURCES:
            raise ConfigurationError(f"DATA_SOURCE must be one of {DATA_SOURCES}, got '{self.data_source}'")
        if self.data_source == "live":
            missing = self.missing_live_settings()
            if missing:
                raise ConfigurationError("Live mode needs these settings: " + ", ".join(missing))

    def missing_live_settings(self) -> list[str]:
        required = {
            "TAVILY_API_KEY": self.tavily_api_key,
            "AVIATION_STACK_API_KEY": self.aviation_stack_api_key,
            "OPENWEATHER_API_KEY": self.openweather_api_key,
            "DATABASE_URL": self.database_url,
            "AVIATIONSTACK_MCP_PYTHON": self.aviationstack_mcp_python,
        }
        return [name for name, value in required.items() if not value]


def _read(env, name: str, default: str = "") -> str:
    """Read one setting as text without spaces at the ends; the default if it is not set."""
    return str(env.get(name, default)).strip()


def _positive_float(text: str, name: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise ConfigurationError(f"{name} must be a number, got '{text}'") from None
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than 0, got {value}")
    return value


def _non_negative_int(text: str, name: str) -> int:
    try:
        value = int(text)
    except ValueError:
        raise ConfigurationError(f"{name} must be a whole number, got '{text}'") from None
    if value < 0:
        raise ConfigurationError(f"{name} must be 0 or more, got {value}")
    return value
