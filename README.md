**Language:** English | [简体中文](README_zh.md)

# Airymax Python SDK

[![Version](https://img.shields.io/badge/version-0.1.1-5a6b7e)](https://atomgit.com/openairymax/sdk-python)
[![License](https://img.shields.io/badge/license-AGPL--3.0+Apache--2.0-4a90d9)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org)

> Official Python development kit for the [Airymax](https://atomgit.com/openairymax/airymaxhub) AI Agent Runtime Platform.
> One of the leaf repositories aggregated by the [sdk](https://atomgit.com/openairymax/sdk) management repo.
> Bundles the official Hooks package (`agentrt.hooks`).

---

## Overview

The **Airymax Python SDK** (`agentrt`) is the production-grade Python interface to the Airymax runtime. It exposes the same double-layer API architecture shared by every Airymax language SDK, plus an official Hooks package that lets agents intercept and shape the runtime pipeline (audit, cost tracking, prompt injection, security reminders).

Agent applications built on this SDK are **runtime tenants**: they invoke system capabilities through the SDK rather than touching kernel internals directly. The SDK provides both synchronous (`AgentRT`) and asynchronous (`AsyncAgentRT`) entry points, full type annotations, context-manager support, OpenTelemetry integration, checkpoint-based resumption, and an LRU-backed token optimizer.

## Double-Layer API Architecture

Every Airymax SDK ships a top-level `AgentRTClient` that nests four resource clients, each covering one plane of the runtime:

```
AgentRTClient
├── CognitionClient   # Cognition plane: tasks / loops / inference
├── SafetyClient      # Safety plane: audit / sandbox / policy
├── ToolClient        # Tool plane: register / invoke / orchestrate
└── ChatClient        # Chat plane: LLM routing / sessions / streaming
```

Python additionally offers the convenience facades `AgentRT` / `AsyncAgentRT`, which expose the four planes through ergonomic, fully-typed methods (e.g. `client.cognition.submit_task(...)`, `client.safety.audit(...)`, `client.tool.invoke(...)`, `client.chat.stream(...)`).

## Directory Structure

```
sdk-python/
├── agentrt/                       # Core package
│   ├── __init__.py                # Public API exports (version, errors, types, client, modules)
│   ├── agent.py                   # AgentRT / AsyncAgentRT sync & async clients
│   ├── client/                    # HTTP client layer
│   │   ├── client.py              # APIClient / ClientConfig / RequestOptions
│   │   └── mock.py                # MockClient for tests
│   ├── modules/                   # Domain module managers
│   │   ├── base_manager.py
│   │   ├── task/                  # TaskManager + Checkpoint
│   │   ├── memory/                # MemoryManager
│   │   ├── session/               # SessionManager
│   │   └── skill/                 # SkillManager
│   ├── hooks/                     # Official Hooks package (agentrt.hooks)
│   │   ├── __init__.py            # BaseHook / HookContext / HookResult
│   │   ├── audit_hook.py          # AuditHook — event auditing
│   │   ├── cost_tracker.py        # CostTrackerHook — token/cost tracking
│   │   ├── prompt_injector.py     # PromptInjectorHook — prompt augmentation
│   │   └── security_reminder.py   # SecurityReminderHook — safety reminders
│   ├── framework/                 # Application framework (lifecycle, plugins, events)
│   ├── telemetry.py               # OpenTelemetry Tracer / Span / Metrics
│   ├── exceptions.py              # Exception hierarchy + error codes
│   ├── types/                     # Enums and domain models
│   ├── utils/                     # Helpers, EventEmitter, TokenOptimizer
│   ├── protocol.py                # Protocol handling
│   └── syscall.py                 # Syscall bindings
├── examples/                      # Usage examples
├── tests/                         # Test suite (unit / e2e / hooks / benchmarks)
├── setup.py                       # setuptools config
├── pyproject.toml                 # PEP 621 metadata
├── requirements.txt               # Dependency pins
└── README.md                      # This file
```

## Upstream & Downstream Dependencies

### Upstream

- **Runtime**: Connects to a running Airymax / AgentRT instance (`gateway_d`) over HTTP and JSON-RPC 2.0.
- **Protocol**: Speaks the AgentsIPC protocol defined in the platform `protocols/` tree.
- **Configuration**: Resolved from constructor arguments, then environment variables (`AGENTRT_ENDPOINT`, `AGENTRT_TIMEOUT`, `AGENTRT_API_KEY`), then a `http://127.0.0.1:18789` default.

### Downstream

- **Agent applications**: User-written agents import `agentrt` to become runtime tenants.
- **CLI / TUI tools**: The Airymax `cli` and `tui` tools can reuse the Python SDK for scripting and extension authoring.
- **Examples**: Reference agents and hook recipes.

## Installation

```bash
# From PyPI (when published)
pip install agentrt

# From source (editable, for development)
cd sdk-python
pip install -e .

# With test extras
pip install -e ".[test]"
```

**Requirements:** Python >= 3.10. Runtime dependencies: `requests`, `aiohttp`, `urllib3`, `asyncio-throttle`, `typing-extensions`. Optional: `opentelemetry-api` / `opentelemetry-sdk` for telemetry, `tiktoken` for precise BPE token counting.

## Quick Start

### Synchronous client

```python
from agentrt import AgentRT

client = AgentRT(endpoint="http://localhost:18789", timeout=30, api_key="key")

task = client.cognition.submit_task('{"input": "analyze this data"}')
result = task.wait(timeout=30)

memory_id = client.memory.write("content", metadata={"tag": "important"})
hits = client.memory.search("query", top_k=5)

client.close()
```

### Asynchronous client

```python
import asyncio
from agentrt import AsyncAgentRT

async def main():
    async with AsyncAgentRT(endpoint="http://localhost:18789") as client:
        task = await client.cognition.submit_task("analyze data")
        result = await task.wait(timeout=30)
        print(result.output)

asyncio.run(main())
```

### Official Hooks package

```python
from agentrt import AgentRT
from agentrt.hooks import SecurityReminderHook, CostTrackerHook, AuditHook

client = AgentRT(endpoint="http://localhost:18789")
client.register_hook(SecurityReminderHook())
client.register_hook(CostTrackerHook())
client.register_hook(AuditHook(log_path="./logs/audit.jsonl"))

# Hooks now observe on_agent_start / on_tool_call / on_llm_request / on_memory_write ...
task = client.cognition.submit_task("summarize the report")
```

Custom hooks subclass `BaseHook` and override only the lifecycle events they need (`on_agent_start`, `on_agent_end`, `on_tool_call`, `on_tool_result`, `on_llm_request`, `on_llm_response`, `on_memory_read`, `on_memory_write`). Returning `HookResult(allowed=False)` aborts the pipeline.

## Configuration

```python
from agentrt import AgentRT, ClientConfig

config = ClientConfig(
    endpoint="http://localhost:18789",
    timeout=30.0,
    max_retries=3,
    api_key="your-api-key",
    user_agent="my-agent/1.0",
)
client = AgentRT(config=config)
```

Environment variables: `AGENTRT_ENDPOINT`, `AGENTRT_TIMEOUT`, `AGENTRT_API_KEY`.

## Build & Test

```bash
# Run the test suite
pytest tests/

# Run a single module
pytest tests/test_agent.py -v

# Run hook tests
pytest tests/hooks/ -v

# Run benchmarks
pytest tests/test_benchmark_performance.py -v
```

## Branch Strategy

This leaf repository is developed on **`feature/official-hubs-01`**. The aggregating `sdk` management repo stays on `main`.

## License

Dual-licensed under **AGPL v3 + Apache 2.0** (SPDX: `AGPL-3.0-or-later OR Apache-2.0`). See [LICENSE](LICENSE) for the full text.

Copyright (c) 2025-2026 **SPHARX Ltd.** All Rights Reserved.
