# SPDX-FileCopyrightText: 2025-2026 SPHARX Ltd.
# SPDX-License-Identifier: AGPL-3.0-or-later OR Apache-2.0

# AgentRT Python SDK - Client Layer
# Version: 0.1.1
# Last updated: 2026-03-24

"""
Client layer providing HTTP communication with AgentRT server.

This module implements the APIClient interface pattern from Go SDK,
providing both sync and async client implementations.

Architecture:
    client/
    ├── __init__.py      # Public API exports
    ├── client.py        # HTTP client implementation
    └── mock.py          # Mock client for testing
"""

from .client import (
    Client,
    APIClient,
    ClientConfig,
    RequestOptions,
    APIResponse,
    HealthStatus,
    Metrics,
)
from .mock import MockClient

__all__ = [
    "Client",
    "APIClient",
    "ClientConfig",
    "RequestOptions",
    "APIResponse",
    "HealthStatus",
    "Metrics",
    "MockClient",
]
