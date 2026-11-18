"""Multi-agent travel planning system (SE423 / SE431 joint project).

Package layout (one sub-package per functional module):

* ``intake``    - Module 1: request validation, guardrail and agent routing
* ``research``  - Module 2: flight / hotel / weather research through MCP adapters
* ``planning``  - Module 3: budget analysis and itinerary planning
* ``workflow``  - Module 4: human approval, persistence, LangGraph workflow, facade

``domain``, ``llm`` and ``shared`` form the shared kernel used by all modules.
"""
