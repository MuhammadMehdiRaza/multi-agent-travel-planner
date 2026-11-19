import asyncio
import threading
import time

import pytest

from travel_planner.research.mcp_gateway import McpToolGateway, describe_error
from travel_planner.shared.exceptions import ExternalServiceError, ResearchTimeoutError, ToolNotFoundError


class FakeTool:
    def __init__(self, name, result="ok", delay=0.0, error=None):
        self.name = name
        self.result = result
        self.delay = delay
        self.error = error
        self.received = []

    async def ainvoke(self, arguments):
        self.received.append(arguments)
        await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.result


class FakeMcpClient:
    """Counts how often the (slow) tool catalogue is loaded."""

    load_count = 0
    lock = threading.Lock()

    def __init__(self, tools):
        self.tools = tools

    async def get_tools(self):
        with FakeMcpClient.lock:
            FakeMcpClient.load_count += 1
        await asyncio.sleep(0.05)  # widen the race window
        return self.tools


def make_gateway(*tools, timeout=5.0):
    FakeMcpClient.load_count = 0
    return McpToolGateway(lambda: FakeMcpClient(list(tools)), call_timeout_seconds=timeout)


def test_calls_tool_with_arguments():
    tool = FakeTool("get_forecast", result={"city": "Rome"})
    gateway = make_gateway(tool)
    assert gateway.call_tool("get_forecast", {"city": "Rome"}) == {"city": "Rome"}
    assert tool.received == [{"city": "Rome"}]


def test_tool_catalogue_is_loaded_only_once_by_concurrent_threads():
    gateway = make_gateway(FakeTool("tavily_search"))
    threads = [threading.Thread(target=gateway.call_tool, args=("tavily_search", {})) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert FakeMcpClient.load_count == 1


def test_unknown_tool_raises_tool_not_found():
    with pytest.raises(ToolNotFoundError, match="list_airports"):
        make_gateway(FakeTool("tavily_search")).call_tool("list_airports", {})


def test_tool_failure_is_wrapped_in_external_service_error():
    gateway = make_gateway(FakeTool("get_forecast", error=RuntimeError("HTTP 401")))
    with pytest.raises(ExternalServiceError, match="HTTP 401"):
        gateway.call_tool("get_forecast", {"city": "Rome"})


def test_slow_tool_raises_timeout():
    gateway = make_gateway(FakeTool("get_forecast", delay=1.0), timeout=0.1)
    start = time.perf_counter()
    with pytest.raises(ResearchTimeoutError):
        gateway.call_tool("get_forecast", {"city": "Rome"})
    assert time.perf_counter() - start < 0.8


def test_failure_to_connect_is_reported_as_external_service_error():
    class BrokenClient:
        async def get_tools(self):
            raise ExceptionGroup("connect", [FileNotFoundError("python.exe not found")])

    gateway = McpToolGateway(BrokenClient, call_timeout_seconds=1)
    with pytest.raises(ExternalServiceError, match="python.exe not found"):
        gateway.call_tool("tavily_search", {})


def test_error_descriptions_hide_api_keys():
    error = RuntimeError("401 for url 'https://mcp.tavily.com/mcp/?tavilyApiKey=tvly-secret&x=1' appid=abc123")
    text = describe_error(error)
    assert "tvly-secret" not in text and "abc123" not in text
    assert "tavilyApiKey=***" in text and "appid=***" in text
