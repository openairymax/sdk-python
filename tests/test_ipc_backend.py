#!/usr/bin/env python
# SPDX-FileCopyrightText: 2025-2026 SPHARX Ltd.
# SPDX-License-Identifier: AGPL-3.0-or-later OR Apache-2.0

# -*- coding: utf-8 -*-
"""``_IpcBackend`` pytest 套件 — Unix socket + JSON-RPC 2.0 后端

覆盖 ``agentrt/syscall.py`` 中 ``_IpcBackend`` 的全部公共方法
(mem.write/get/search/delete + agent.spawn/terminate/invoke/list +
tool.execute_tool)，重试容错 (BrokenPipe/ConnectionReset/socket.timeout) 与
``_extract_result`` 错误解析。

测试不依赖真实 mem_d / agent_d 守护进程：通过 mock ``_call_once``
方法直接返回预设 result dict 或抛出指定异常，验证各公共方法的
参数封装、结果解析与重试逻辑。

对齐 ``airymax-agent-standard.md`` §10
验证清单 "_IpcBackend pytest 全绿"。
"""

import json
import os
import socket
import sys
from unittest.mock import MagicMock

import pytest

# 确保父目录（agentrt 包所在目录）在 sys.path 中
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from agentrt.syscall import (  # noqa: E402
    _IpcBackend,
    SyscallError,
    SyscallProxy,
    _IPC_MAX_RETRIES,
)
from agentrt.exceptions import (  # noqa: E402
    CODE_MEMORY_NOT_FOUND,
    ValidationError,
)


# ── 辅助工具 ──────────────────────────────────────────────


def _make_backend_with_result(result):
    """构造 ``_IpcBackend`` 实例，mock ``_call_once`` 返回 ``result``。

    ``_call_once`` 在生产代码中返回 ``_extract_result(...)`` 的结果
    （即 JSON-RPC response 的 ``result`` 字段，已解析为 Python 对象），
    故此处直接返回 ``result`` dict / list 即可模拟 daemon 成功响应。
    """
    backend = _IpcBackend()
    backend._call_once = MagicMock(return_value=result)
    return backend


def _make_backend_with_side_effect(side_effect):
    """构造 ``_IpcBackend`` 实例，mock ``_call_once`` 按预设副作用执行。

    用于重试测试：``side_effect`` 可为异常列表或单个异常。
    """
    backend = _IpcBackend()
    backend._call_once = MagicMock(side_effect=side_effect)
    return backend


def _captured_params(mock_call_once):
    """从 ``_call_once`` mock 的调用参数中提取 JSON-RPC ``params`` dict。

    ``_call`` 将 request 序列化为 payload 传给 ``_call_once(socket_path, payload)``；
    反序列化 payload 即可拿到原始 ``params``，用于验证参数封装正确性。
    """
    assert mock_call_once.call_count >= 1, "expected _call_once to be invoked"
    args, _kwargs = mock_call_once.call_args
    # _call_once(socket_path, payload)
    payload = args[1]
    request = json.loads(payload.decode("utf-8"))
    return request["params"]


# ── mem_d 方法 ────────────────────────────────────────────


def test_memory_write_returns_record_id():
    """memory_write 返回 daemon 分配的 record_id 字符串。"""
    backend = _make_backend_with_result({"record_id": "abc123"})
    assert backend.memory_write(b"hello", None) == "abc123"


def test_memory_write_with_metadata_dict():
    """metadata 为合法 JSON 字符串时，应解析为 dict 传给 params.metadata。"""
    backend = _make_backend_with_result({"record_id": "r1"})
    backend.memory_write(b"hello", '{"topic":"test"}')
    params = _captured_params(backend._call_once)
    assert params["metadata"] == {"topic": "test"}


def test_memory_write_with_metadata_plain_string():
    """metadata 为非 JSON 字符串时，应原样透传为字符串。"""
    backend = _make_backend_with_result({"record_id": "r1"})
    backend.memory_write(b"hello", "not-json")
    params = _captured_params(backend._call_once)
    assert params["metadata"] == "not-json"


def test_memory_get_returns_bytes():
    """memory_get 返回 daemon 数据，编码为 bytes。"""
    backend = _make_backend_with_result({"data": "hello world"})
    assert backend.memory_get("rid") == b"hello world"


def test_memory_get_record_not_found():
    """daemon 返回结果中无 data 字段时，SDK 抛 SyscallError (CODE_MEMORY_NOT_FOUND)。"""
    backend = _make_backend_with_result({})
    with pytest.raises(SyscallError) as exc_info:
        backend.memory_get("missing-rid")
    assert exc_info.value.error_code_int == CODE_MEMORY_NOT_FOUND


def test_memory_search_returns_tuples():
    """memory_search 返回 [(record_id, score), ...] 元组列表。"""
    backend = _make_backend_with_result(
        {"results": [{"record_id": "r1", "score": 0.9},
                      {"record_id": "r2", "score": 0.5}]}
    )
    assert backend.memory_search("query", 10) == [("r1", 0.9), ("r2", 0.5)]


def test_memory_search_empty_results():
    """memory_search 在无结果时返回空列表（兼容 {} 与 {"results":[]}）。"""
    backend = _make_backend_with_result({"results": []})
    assert backend.memory_search("query", 10) == []
    backend2 = _make_backend_with_result({})
    assert backend2.memory_search("query", 10) == []


def test_memory_delete_returns_true():
    """memory_delete 成功时返回 True。"""
    backend = _make_backend_with_result({})
    assert backend.memory_delete("rid") is True


# ── agent_d 方法 ──────────────────────────────────────────


def test_agent_spawn_returns_agent_id():
    """agent_spawn 返回 daemon 分配的 agent_id 字符串。"""
    backend = _make_backend_with_result({"agent_id": "a1"})
    assert backend.agent_spawn('{"role":"pm"}') == "a1"


def test_agent_spawn_accepts_json_string_spec():
    """agent_spec 为合法 JSON 字符串时，应解析为 dict 传给 params.agent_spec。"""
    backend = _make_backend_with_result({"agent_id": "a1"})
    backend.agent_spawn('{"role":"pm"}')
    params = _captured_params(backend._call_once)
    assert params["agent_spec"] == {"role": "pm"}


def test_agent_spawn_accepts_non_json_spec():
    """agent_spec 为非 JSON 字符串时，应原样透传为字符串。"""
    backend = _make_backend_with_result({"agent_id": "a1"})
    backend.agent_spawn("plain text")
    params = _captured_params(backend._call_once)
    assert params["agent_spec"] == "plain text"


def test_agent_terminate_returns_true():
    """agent_terminate 成功时返回 True。"""
    backend = _make_backend_with_result({})
    assert backend.agent_terminate("a1") is True


def test_agent_invoke_returns_output():
    """agent_invoke 返回 daemon 输出字符串。"""
    backend = _make_backend_with_result({"output": "result text"})
    assert backend.agent_invoke("a1", "input") == "result text"


def test_agent_invoke_bad_result_raises():
    """daemon 返回结果中无 output 字段时，SDK 抛 SyscallError。"""
    backend = _make_backend_with_result({})
    with pytest.raises(SyscallError):
        backend.agent_invoke("a1", "input")


def test_agent_list_returns_strings():
    """agent_list 返回 agent_id 字符串列表。"""
    backend = _make_backend_with_result({"agent_ids": ["a1", "a2"]})
    assert backend.agent_list() == ["a1", "a2"]


def test_agent_list_filters_non_string():
    """agent_list 过滤掉非字符串条目（int/None 等）。"""
    backend = _make_backend_with_result(
        {"agent_ids": ["a1", 42, None, "a2"]}
    )
    assert backend.agent_list() == ["a1", "a2"]


# ── tool_d 方法 ──────────────────────────────────────────


def test_tool_execute_returns_result_dict():
    """tool_execute 返回 daemon 原始结果 dict（success/output/error/exit_code）。"""
    backend = _make_backend_with_result(
        {"success": True, "output": "file content", "error": "", "exit_code": 0}
    )
    result = backend.tool_execute("fs_read", {"path": "/tmp/a.txt"})
    assert result["success"] is True
    assert result["output"] == "file content"
    params = _captured_params(backend._call_once)
    assert params["tool_id"] == "fs_read"
    assert params["params"] == {"path": "/tmp/a.txt"}


def test_tool_execute_non_dict_params_coerced_to_empty():
    """tool_execute 的 params 非 dict 时，应透传为空对象（与 tool_d 兼容）。"""
    backend = _make_backend_with_result(
        {"success": False, "error": "missing params", "exit_code": 1}
    )
    backend.tool_execute("shell_run", "ls -la")
    params = _captured_params(backend._call_once)
    assert params["params"] == {}


def test_tool_execute_bad_result_raises():
    """daemon 返回结果非 dict 时，SDK 抛 SyscallError。"""
    backend = _make_backend_with_result(["not", "a", "dict"])
    with pytest.raises(SyscallError):
        backend.tool_execute("fs_read", {"path": "/tmp/a.txt"})


def test_tool_execute_uses_tool_socket():
    """tool_execute 应直连 tool.sock（默认 $AIRY_RUNTIME_DIR/tool.sock）。"""
    backend = _make_backend_with_result(
        {"success": True, "output": "ok", "error": "", "exit_code": 0}
    )
    backend.tool_execute("fs_list", {"path": "/tmp"})
    args, _kwargs = backend._call_once.call_args
    assert args[0].endswith("tool.sock")


# ── 重试容错 ──────────────────────────────────────────────


@pytest.fixture
def fast_retries(monkeypatch):
    """关闭重试退避 sleep，加速重试测试。"""
    monkeypatch.setattr("agentrt.syscall._IPC_RETRY_BACKOFF_S", 0)


def test_retry_on_broken_pipe(fast_retries):
    """前 2 次 BrokenPipeError，第 3 次成功 → 最终成功，调用 3 次。"""
    backend = _make_backend_with_side_effect(
        [BrokenPipeError("fail-1"), BrokenPipeError("fail-2"),
         {"record_id": "ok"}]
    )
    assert backend.memory_write(b"hello", None) == "ok"
    assert backend._call_once.call_count == 3


def test_retry_on_connection_reset(fast_retries):
    """前 2 次 ConnectionResetError，第 3 次成功 → 最终成功，调用 3 次。"""
    backend = _make_backend_with_side_effect(
        [ConnectionResetError("fail-1"), ConnectionResetError("fail-2"),
         {"record_id": "ok"}]
    )
    assert backend.memory_write(b"hello", None) == "ok"
    assert backend._call_once.call_count == 3


def test_retry_on_socket_timeout(fast_retries):
    """前 2 次 socket.timeout，第 3 次成功 → 最终成功，调用 3 次。"""
    backend = _make_backend_with_side_effect(
        [socket.timeout("fail-1"), socket.timeout("fail-2"),
         {"record_id": "ok"}]
    )
    assert backend.memory_write(b"hello", None) == "ok"
    assert backend._call_once.call_count == 3


def test_retry_exhausted_raises_syscall_error(fast_retries):
    """全部 1+_IPC_MAX_RETRIES 次都失败 → 抛 SyscallError。

    _IPC_MAX_RETRIES=3 → 总尝试 4 次 (1 初次 + 3 重试)。
    """
    total_attempts = _IPC_MAX_RETRIES + 1
    backend = _make_backend_with_side_effect(
        [BrokenPipeError(f"fail-{i}") for i in range(total_attempts)]
    )
    with pytest.raises(SyscallError) as exc_info:
        backend.memory_write(b"hello", None)
    assert "failed after retries" in exc_info.value.message
    assert backend._call_once.call_count == total_attempts


def test_call_propagates_other_exceptions(fast_retries):
    """非重试类型异常 (ValueError) 应直接传播，不重试。"""
    backend = _make_backend_with_side_effect(ValueError("not retryable"))
    with pytest.raises(ValueError):
        backend.memory_write(b"hello", None)
    assert backend._call_once.call_count == 1


# ── _extract_result 错误解析 ─────────────────────────────


def test_extract_result_with_jsonrpc_error():
    """daemon 返回 JSON-RPC error 时，_extract_result 抛 SyscallError 含 error_code。"""
    with pytest.raises(SyscallError) as exc_info:
        _IpcBackend._extract_result(
            '{"jsonrpc":"2.0","error":{"code":-32000,"message":"bad"},"id":1}'
        )
    assert exc_info.value.error_code_int == -32000


def test_extract_result_malformed_response():
    """非 JSON 响应：_extract_result 抛 json.JSONDecodeError (ValueError 子类)。

    注：``_extract_result`` 直接调用 ``json.loads`` 且未捕获 JSONDecodeError，
    故畸形 JSON 抛 json.JSONDecodeError 而非 SyscallError（生产代码在
    ``_call_once`` 中捕获并重试，最终以 ConnectionResetError/超时形式暴露）。
    """
    import json as _json
    with pytest.raises(_json.JSONDecodeError):
        _IpcBackend._extract_result("not json")


def test_extract_result_missing_result_field():
    """响应无 result 字段（也无 error）时抛 SyscallError。"""
    with pytest.raises(SyscallError) as exc_info:
        _IpcBackend._extract_result('{"jsonrpc":"2.0","id":1}')
    assert "missing 'result'" in exc_info.value.message


# ── 通用 svc_call ────────────────────────────────────────


def test_svc_call_routes_to_mem_socket():
    """daemon=mem 应直连 mem.sock，params 原样下发，result 原样返回。"""
    backend = _make_backend_with_result({"ok": True})
    assert backend.svc_call("mem", "stats", {"k": "v"}) == {"ok": True}
    args, _kwargs = backend._call_once.call_args
    assert args[0].endswith("mem.sock")
    assert _captured_params(backend._call_once) == {"k": "v"}


def test_svc_call_routes_to_agent_socket():
    """daemon=agent 应直连 agent.sock，list 结果原样返回。"""
    backend = _make_backend_with_result(["a1", "a2"])
    assert backend.svc_call("agent", "status") == ["a1", "a2"]
    args, _kwargs = backend._call_once.call_args
    assert args[0].endswith("agent.sock")


def test_svc_call_routes_to_tool_socket():
    """daemon=tool 应直连 tool.sock。"""
    backend = _make_backend_with_result({"ok": True})
    backend.svc_call("tool", "metrics")
    args, _kwargs = backend._call_once.call_args
    assert args[0].endswith("tool.sock")


def test_svc_call_none_params_becomes_empty_object():
    """params 省略时按空对象下发（JSON-RPC 要求 object 形态）。"""
    backend = _make_backend_with_result({})
    backend.svc_call("mem", "stats")
    assert _captured_params(backend._call_once) == {}


def test_svc_call_rejects_unknown_daemon():
    """daemon 名不在 mem/agent/tool 内时抛 ValidationError，且不下发。"""
    backend = _make_backend_with_result({})
    with pytest.raises(ValidationError):
        backend.svc_call("llm", "status")
    assert backend._call_once.call_count == 0


def test_svc_call_rejects_empty_method():
    """method 为空串时抛 ValidationError，且不下发。"""
    backend = _make_backend_with_result({})
    with pytest.raises(ValidationError):
        backend.svc_call("agent", "")
    assert backend._call_once.call_count == 0


def test_proxy_svc_call_delegates_to_ipc():
    """SyscallProxy.svc_call 在 IPC 后端下委派给 _IpcBackend.svc_call。"""
    proxy = object.__new__(SyscallProxy)
    proxy._backend = "ipc"
    proxy._ipc = _make_backend_with_result({"x": 1})
    assert proxy.svc_call("status") == {"x": 1}


def test_proxy_svc_call_requires_ipc_backend():
    """FFI 后端没有通用派发面，svc_call 抛 SyscallError 而非返回空值。"""
    proxy = object.__new__(SyscallProxy)
    proxy._backend = "ffi"
    proxy._ipc = None
    with pytest.raises(SyscallError):
        proxy.svc_call("status")


def test_proxy_svc_call_rejects_non_dict_params():
    """params 非 dict（非 None）时抛 ValidationError。"""
    proxy = object.__new__(SyscallProxy)
    proxy._backend = "ipc"
    proxy._ipc = _make_backend_with_result({})
    with pytest.raises(ValidationError):
        proxy.svc_call("status", ["not", "a", "dict"])
