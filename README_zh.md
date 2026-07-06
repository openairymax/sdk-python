**语言:** [English](README.md) | 简体中文

# Airymax Python SDK

[![Version](https://img.shields.io/badge/version-0.1.1-5a6b7e)](https://atomgit.com/openairymax/sdk-python)
[![License](https://img.shields.io/badge/license-AGPL--3.0+Apache--2.0-4a90d9)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)](https://www.python.org)

> [Airymax](https://atomgit.com/openairymax/airymaxhub) AI 智能体运行时平台的官方 Python 开发工具包。
> [sdk](https://atomgit.com/openairymax/sdk) 管理仓聚合的叶子仓之一。
> 内置官方 Hooks 包（`agentrt.hooks`）。

---

## 概述

**Airymax Python SDK**（`agentrt`）是 Airymax 运行时的生产级 Python 接口。它实现了所有 Airymax 语言 SDK 共享的双层 API 架构，并附带官方 Hooks 包，让 Agent 能够拦截并塑造运行时管线（审计、成本追踪、Prompt 注入、安全提醒）。

基于该 SDK 构建的 Agent 应用是**运行时租户**：通过 SDK 调用系统能力，而非直接访问内核内部。SDK 同时提供同步（`AgentRT`）与异步（`AsyncAgentRT`）入口、完整的类型注解、上下文管理器支持、OpenTelemetry 集成、Checkpoint 断点续传以及基于 LRU 的 Token 优化器。

## 双层 API 架构

每个 Airymax SDK 都提供顶层 `AgentRTClient`，内嵌四个资源客户端，分别覆盖运行时的一个平面：

```
AgentRTClient
├── CognitionClient   # 认知平面：任务 / 循环 / 推理
├── SafetyClient      # 安全平面：审计 / 沙箱 / 策略
├── ToolClient        # 工具平面：注册 / 调用 / 编排
└── ChatClient        # 对话平面：LLM 路由 / 会话 / 流式
```

Python 额外提供便捷外观 `AgentRT` / `AsyncAgentRT`，通过符合人体工程学、完整类型化的方法暴露四个平面（如 `client.cognition.submit_task(...)`、`client.safety.audit(...)`、`client.tool.invoke(...)`、`client.chat.stream(...)`）。

## 目录结构

```
sdk-python/
├── agentrt/                       # 核心包
│   ├── __init__.py                # 公共 API 导出（版本、异常、类型、客户端、模块）
│   ├── agent.py                   # AgentRT / AsyncAgentRT 同步与异步客户端
│   ├── client/                    # HTTP 客户端层
│   │   ├── client.py              # APIClient / ClientConfig / RequestOptions
│   │   └── mock.py                # 测试用 MockClient
│   ├── modules/                   # 业务模块管理器
│   │   ├── base_manager.py
│   │   ├── task/                  # TaskManager + Checkpoint
│   │   ├── memory/                # MemoryManager
│   │   ├── session/               # SessionManager
│   │   └── skill/                 # SkillManager
│   ├── hooks/                     # 官方 Hooks 包（agentrt.hooks）
│   │   ├── __init__.py            # BaseHook / HookContext / HookResult
│   │   ├── audit_hook.py          # AuditHook — 事件审计
│   │   ├── cost_tracker.py        # CostTrackerHook — Token / 成本追踪
│   │   ├── prompt_injector.py     # PromptInjectorHook — Prompt 增强
│   │   └── security_reminder.py   # SecurityReminderHook — 安全提醒
│   ├── framework/                 # 应用框架（生命周期、插件、事件）
│   ├── telemetry.py               # OpenTelemetry Tracer / Span / Metrics
│   ├── exceptions.py              # 异常层级与错误码
│   ├── types/                     # 枚举与领域模型
│   ├── utils/                     # 工具函数、EventEmitter、TokenOptimizer
│   ├── protocol.py                # 协议处理
│   └── syscall.py                 # 系统调用绑定
├── examples/                      # 使用示例
├── tests/                         # 测试套件（单元 / 端到端 / hooks / 基准）
├── setup.py                       # setuptools 配置
├── pyproject.toml                 # PEP 621 元数据
├── requirements.txt               # 依赖版本锁定
└── README.md                      # 本文件
```

## 上下游依赖

### 上游

- **运行时**：通过 HTTP 和 JSON-RPC 2.0 连接到运行中的 Airymax / AgentRT 实例（`gateway_d`）。
- **协议**：使用平台 `protocols/` 中定义的 AgentsIPC 协议。
- **配置**：依次从构造参数、环境变量（`AGENTRT_ENDPOINT`、`AGENTRT_TIMEOUT`、`AGENTRT_API_KEY`）、默认值 `http://127.0.0.1:18789` 解析。

### 下游

- **Agent 应用**：用户编写的 Agent 导入 `agentrt` 成为运行时租户。
- **CLI / TUI 工具**：Airymax 的 `cli` 和 `tui` 工具可复用 Python SDK 进行脚本编写和扩展开发。
- **示例**：参考 Agent 与 Hooks 用法示例。

## 安装

```bash
# 从 PyPI 安装（发布后）
pip install agentrt

# 从源码安装（开发可编辑模式）
cd sdk-python
pip install -e .

# 含测试 extras
pip install -e ".[test]"
```

**环境要求：** Python >= 3.10。运行时依赖：`requests`、`aiohttp`、`urllib3`、`asyncio-throttle`、`typing-extensions`。可选：`opentelemetry-api` / `opentelemetry-sdk`（遥测）、`tiktoken`（精确 BPE Token 计数）。

## 快速入门

### 同步客户端

```python
from agentrt import AgentRT

client = AgentRT(endpoint="http://localhost:18789", timeout=30, api_key="key")

task = client.cognition.submit_task('{"input": "analyze this data"}')
result = task.wait(timeout=30)

memory_id = client.memory.write("content", metadata={"tag": "important"})
hits = client.memory.search("query", top_k=5)

client.close()
```

### 异步客户端

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

### 官方 Hooks 包

```python
from agentrt import AgentRT
from agentrt.hooks import SecurityReminderHook, CostTrackerHook, AuditHook

client = AgentRT(endpoint="http://localhost:18789")
client.register_hook(SecurityReminderHook())
client.register_hook(CostTrackerHook())
client.register_hook(AuditHook(log_path="./logs/audit.jsonl"))

# Hooks 现在会观察 on_agent_start / on_tool_call / on_llm_request / on_memory_write ...
task = client.cognition.submit_task("summarize the report")
```

自定义 Hook 继承 `BaseHook`，按需覆写生命周期事件（`on_agent_start`、`on_agent_end`、`on_tool_call`、`on_tool_result`、`on_llm_request`、`on_llm_response`、`on_memory_read`、`on_memory_write`）。返回 `HookResult(allowed=False)` 可中止管线。

## 配置

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

环境变量：`AGENTRT_ENDPOINT`、`AGENTRT_TIMEOUT`、`AGENTRT_API_KEY`。

## 构建与测试

```bash
# 运行测试套件
pytest tests/

# 运行单个模块
pytest tests/test_agent.py -v

# 运行 hooks 测试
pytest tests/hooks/ -v

# 运行基准测试
pytest tests/test_benchmark_performance.py -v
```

## 分支策略

本叶子仓在 **`feature/official-hubs-01`** 分支上开发。聚合管理仓 `sdk` 仅使用 `main` 分支。

## 许可证

采用 **AGPL v3 + Apache 2.0** 双许可证（SPDX: `AGPL-3.0-or-later OR Apache-2.0`）。详见 [LICENSE](LICENSE)。

Copyright (c) 2025-2026 **SPHARX Ltd.** All Rights Reserved.
