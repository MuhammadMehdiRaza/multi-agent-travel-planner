"""Thread-safe access to the tools exposed by the MCP servers.

Thread-safety strategy (see the design document for the full discussion):
  * The list of MCP tools is loaded lazily, the first time a tool is needed.
    Loading is slow (it starts the MCP servers), so it is protected by a
    threading.Lock: if several research threads ask at the same moment,
    exactly one loads the tools and the others wait and reuse the result.
  * After loading, the tool dictionary is only read, never modified.
  * Every tool call runs in its own asyncio event loop (asyncio.run) inside
    the calling worker thread, so threads never share an event loop.
"""

import asyncio
import re
import threading
from abc import ABC, abstractmethod

from travel_planner.shared.exceptions import ExternalServiceError, ResearchTimeoutError, ToolNotFoundError

SECRET_IN_URL = re.compile(r"((?:api_?key|apikey|appid|key|token)=)[^&\s'\"]+", re.IGNORECASE)


class ToolGateway(ABC):
    """Interface used by the MCP adapters (lets tests replace the real MCP servers)."""

    @abstractmethod
    def call_tool(self, tool_name: str, arguments: dict):
        """Call an MCP tool and return its raw result."""


# SOLID - SRP: only loads and calls MCP tools; the adapters translate, the agents decide.
# Thread safety: the tool list is loaded once, lazily, under a lock (agents call it in parallel).
class McpToolGateway(ToolGateway):
    def __init__(self, client_factory, call_timeout_seconds: float = 30.0):
        self._client_factory = client_factory  # function that creates a MultiServerMCPClient
        self._timeout = call_timeout_seconds
        self._tools = None  # dict: tool name -> tool, filled on first use
        self._lock = threading.Lock()

    def call_tool(self, tool_name: str, arguments: dict):
        tool = self._get_tool(tool_name)
        try:
            return asyncio.run(asyncio.wait_for(tool.ainvoke(arguments), timeout=self._timeout))
        except TimeoutError as error:
            raise ResearchTimeoutError(tool_name, f"no answer within {self._timeout} seconds") from error
        except Exception as error:  # MCP / HTTP libraries raise many types; convert them to one of ours
            raise ExternalServiceError(tool_name, describe_error(error)) from error

    def _get_tool(self, tool_name: str):
        tools = self._load_tools()
        if tool_name not in tools:
            known = ", ".join(sorted(tools)) or "none"
            raise ToolNotFoundError(tool_name, f"tool is not available (available tools: {known})")
        return tools[tool_name]

    def _load_tools(self) -> dict:
        with self._lock:  # only one thread may load the tools
            if self._tools is None:
                client = self._client_factory()
                try:
                    tools = asyncio.run(client.get_tools())
                except Exception as error:  # connection problems arrive as ExceptionGroups
                    raise ExternalServiceError("mcp", "could not load tools: " + describe_error(error)) from error
                self._tools = {tool.name: tool for tool in tools}
            return self._tools


def hide_secrets(text: str) -> str:
    """Mask API keys that appear in URLs (Tavily puts its key in the URL, OpenWeatherMap uses appid=)."""
    return SECRET_IN_URL.sub(r"\1***", text)


def describe_error(error: BaseException) -> str:
    """Readable message, including the inner errors of an ExceptionGroup. API keys are masked."""
    inner_errors = getattr(error, "exceptions", None)
    if inner_errors:
        return "; ".join(describe_error(inner) for inner in inner_errors)
    return hide_secrets(f"{type(error).__name__}: {error}")


def live_mcp_connections(settings) -> dict:
    """Connection settings for the three MCP servers (formerly hard-coded in mcp_client.py)."""
    return {
        "tavily": {
            "transport": "streamable_http",
            "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={settings.tavily_api_key}",
        },
        "aviationstack": {
            "transport": "stdio",
            "command": settings.aviationstack_mcp_python,
            "args": ["-m", "aviationstack_mcp", "mcp", "run"],
            "env": {"AVIATION_STACK_API_KEY": settings.aviation_stack_api_key},
        },
        "weather": {
            "transport": "stdio",
            "command": settings.weather_mcp_python,
            "args": [settings.weather_mcp_script],
            "env": {"OPENWEATHER_API_KEY": settings.openweather_api_key},
        },
    }
