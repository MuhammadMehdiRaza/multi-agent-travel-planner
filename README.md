# Multi-Agent Travel Planner

A multi-agent AI system that turns a natural-language travel request (for example
*"Plan a 7-day Japan trip under 2 lakhs"*) into a researched, budget-checked and
human-approved travel plan. A supervisor routes the request to specialist agents for
flights, hotels, weather and budget. The agents gather live data through MCP servers.
A human reviews the draft before the final plan is produced and saved.

Semester project for **SE423 Software Construction and Development** and
**SE431 Software Quality Assurance** (Fall 2026).

| Team member | Registration no. | Primary ownership |
|---|---|---|
| Ahmed Yar Durrani | 2023076 | Team Lead; Module 4 - Approval Workflow & Persistence |
| Mian Muhammad Owais | 2023316 | Module 1 - Request Intake & Guardrails; Module 3 - Budget & Itinerary Planning; 5.3 LLM reliability decorators |
| Muhammad Mehdi Raza | 2023466 | Module 2 - Travel Research Integration; Module 5 - Shared Kernel; 4.4 integration factories |

> **Status - Milestone 1 (design baseline).** This repository currently holds the project
> documentation and branch strategy. The implementation is being built test-first on
> feature branches and will be merged into `main` through reviewed pull requests for Milestone 2.

---

## Modules

Modules 1-4 are the functional modules. Module 5 is a supporting module with the code all of them share.

| # | Module | Scope (one line) |
|---|---|---|
| 1 | Request Intake & Guardrails | Validates the request, blocks off-topic and prompt-injection input, extracts trip constraints and selects the agents to run. |
| 2 | Travel Research Integration | Collects flight, hotel and weather information through MCP servers; the three research agents run concurrently. |
| 3 | Budget & Itinerary Planning | Parses the budget, estimates the trip cost, gives a FEASIBLE / TIGHT / OVER_BUDGET verdict and drafts the itinerary. |
| 4 | Approval Workflow & Persistence | Pauses for human approval with a bounded revision loop, stores plans and approval decisions, exposes one facade to the UI; its composition root (4.4) builds the live or sample objects. |
| 5 | Shared Kernel (supporting) | Domain value objects (5.1), the `LLMClient` interface and Groq adapter (5.2), logging and retry decorators for LLM calls (5.3), and the error types, settings and JSON reading (5.4). |

Design highlights: SOLID-based object-oriented design, plus the Abstract Factory, Adapter,
Facade, Decorator and Strategy patterns. The design document submitted for Milestone 1
explains each one.

## Technology

Python 3.11+ · LangGraph · LangChain · Groq (openai/gpt-oss-120b) · Model Context Protocol (MCP) ·
Tavily · AviationStack · OpenWeatherMap · PostgreSQL / SQLite · Streamlit · pytest · pylint · GitHub Actions

---

## Setup

The setup below applies from Milestone 2, when the code is merged into `main`.

### 1. Prerequisites

- Python 3.11 or newer, and Git
- A free Groq API key: <https://console.groq.com>
- For **live mode** only: PostgreSQL, API keys for Tavily, AviationStack and OpenWeatherMap
  (the free plans are enough), and the `uv` package manager (`pip install uv`)

### 2. Clone and install

```bash
git clone https://github.com/MuhammadMehdiRaza/multi-agent-travel-planner.git
cd multi-agent-travel-planner
python -m venv .venv
# Windows:            .venv\Scripts\activate
# macOS / Linux:      source .venv/bin/activate
pip install -r requirements-dev.txt
```

### 3. Configure

Copy `.env.example` to `.env` and fill in the values. **Never commit `.env`.**

| Mode | `DATA_SOURCE` | What you need |
|---|---|---|
| Sample (default) | `sample` | Only `GROQ_API_KEY`. Uses labelled built-in sample travel data and a local SQLite file; only the Groq AI is reached over the internet. |
| Live | `live` | All keys in `.env.example`, a PostgreSQL database and the AviationStack MCP server (step 4). |

### 4. Live mode only

1. Create the database (the tables are created automatically on first run):
   ```sql
   CREATE DATABASE travel_planner;
   ```
   Then set `DATABASE_URL`, for example `postgresql://postgres:<password>@localhost:5432/travel_planner`.
2. Install the AviationStack MCP server in its own folder:
   ```bash
   git clone https://github.com/Pradumnasaraf/aviationstack-mcp.git
   cd aviationstack-mcp
   uv sync
   ```
   Set `AVIATIONSTACK_MCP_PYTHON` to the Python interpreter inside its `.venv`
   (for example `C:\tools\aviationstack-mcp\.venv\Scripts\python.exe`).
3. The weather MCP server (`weather_mcp_server.py`) and the Tavily MCP server
   (hosted) are started automatically. No extra step is needed.

### 5. Run

```bash
streamlit run frontend.py
```

Example request: *Plan a complete 7 days Japan trip including flights, hotels and sightseeing under 2 lakhs.*

### 6. Test and check quality

```bash
pytest                                            # all unit and integration tests
pytest --cov=travel_planner --cov-report=term     # with coverage
pylint travel_planner weather_mcp_server.py       # static analysis
radon cc travel_planner -a                        # cyclomatic complexity
```

From Milestone 2, the CI pipeline (`.github/workflows/ci.yml`) runs the tests, a 60% coverage
gate and a pylint quality gate on every push and pull request.

---

## Contributing and branch strategy

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branching model, pull-request rules, the
test-first commit convention and milestone baselines.

## Acknowledgement

The initial prototype was adapted from the public tutorial repository
[codewithaarohi/Multi_agent_system_part_3](https://github.com/codewithaarohi/Multi_agent_system_part_3).
It is kept in the history as the "before" baseline. The architecture, refactoring, new
modules, tests and documentation are the team's own work. Use of AI assistants is
recorded in the AI Usage Log submitted with each milestone, as the course guidelines require.
