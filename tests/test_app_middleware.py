from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Callable, Generator
from unittest.mock import ANY

import pytest
from key_value.aio.stores.memory import MemoryStore


class StubLoggingMiddleware:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class StubErrorHandlingMiddleware:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class StubRetryMiddleware:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class StubResponseCachingMiddleware:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class StubEunomiaMiddleware:
    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs


class StubASGIApp:
    def __init__(self) -> None:
        self.middleware: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def add_middleware(self, *args: object, **kwargs: object) -> None:
        self.middleware.append((args, kwargs))


class StubMCP:
    def __init__(self, name: str, instructions: str, **_: object) -> None:
        self.name = name
        self.instructions = instructions
        self.added: list[object] = []
        self.prompts: list[
            tuple[object, tuple[object, ...], dict[str, object]]
        ] = []
        self.tools: list[
            tuple[object, tuple[object, ...], dict[str, object]]
        ] = []
        self.routes: list[
            tuple[object, tuple[object, ...], dict[str, object]]
        ] = []
        self.transport: str | None = None

    def add_middleware(self, middleware: object) -> None:
        self.added.append(middleware)

    def prompt(
        self, *args: object, **kwargs: object
    ) -> Callable[[object], object]:
        def decorator(func: object) -> object:
            self.prompts.append((func, args, kwargs))
            return func

        return decorator

    def tool(
        self, *args: object, **kwargs: object
    ) -> Callable[[object], object]:
        def decorator(func: object) -> object:
            self.tools.append((func, args, kwargs))
            return func

        return decorator

    def custom_route(
        self, *args: object, **kwargs: object
    ) -> Callable[[object], object]:
        def decorator(func: object) -> object:
            self.routes.append((func, args, kwargs))
            return func

        return decorator

    def http_app(self, transport: str) -> StubASGIApp:
        self.transport = transport
        return StubASGIApp()


@pytest.fixture(autouse=True)
def _reset_app_module() -> Generator[None, None, None]:
    import powersearch_mcp.app as app_module

    yield

    os.environ.pop("POWERSEARCH_AUTHZ_POLICY_PATH", None)

    settings_module = importlib.import_module("powersearch_mcp.settings")
    importlib.reload(settings_module)

    importlib.reload(app_module)


def test_app_wires_middleware_with_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FASTMCP_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("POWERSEARCH_INCLUDE_PAYLOADS", "true")
    monkeypatch.setenv("POWERSEARCH_INCLUDE_PAYLOAD_LENGTH", "true")
    monkeypatch.setenv("POWERSEARCH_ESTIMATE_PAYLOAD_TOKENS", "true")
    monkeypatch.setenv("POWERSEARCH_MAX_PAYLOAD_LENGTH", "256")
    monkeypatch.setenv("POWERSEARCH_ERRORHANDLING_TRACEBACK", "true")
    monkeypatch.setenv("POWERSEARCH_ERRORHANDLING_TRANSFORM", "false")
    monkeypatch.setenv("POWERSEARCH_RETRY_RETRIES", "4")
    monkeypatch.setenv("POWERSEARCH_RETRY_BASE_DELAY", "0.25")
    monkeypatch.setenv("POWERSEARCH_RETRY_MAX_DELAY", "5")
    monkeypatch.setenv("POWERSEARCH_RETRY_BACKOFF_MULTIPLIER", "3.0")

    monkeypatch.setattr("fastmcp.server.FastMCP", StubMCP)
    monkeypatch.setattr(
        "fastmcp.server.middleware.logging.LoggingMiddleware",
        StubLoggingMiddleware,
    )
    monkeypatch.setattr(
        "fastmcp.server.middleware.error_handling.ErrorHandlingMiddleware",
        StubErrorHandlingMiddleware,
    )
    monkeypatch.setattr(
        "fastmcp.server.middleware.error_handling.RetryMiddleware",
        StubRetryMiddleware,
    )
    monkeypatch.setattr(
        "fastmcp.server.middleware.caching.ResponseCachingMiddleware",
        StubResponseCachingMiddleware,
    )

    settings_module = importlib.import_module("powersearch_mcp.settings")
    importlib.reload(settings_module)

    app_module = importlib.import_module("powersearch_mcp.app")
    importlib.reload(app_module)

    mcp = app_module.mcp  # attribute provided by app module

    assert isinstance(mcp, StubMCP)
    assert len(mcp.added) == 3

    logging_mw, error_mw, retry_mw = mcp.added
    assert isinstance(logging_mw, StubLoggingMiddleware)
    assert logging_mw.kwargs == {
        "log_level": pytest.approx(30),
        "include_payloads": True,
        "include_payload_length": True,
        "estimate_payload_tokens": True,
        "max_payload_length": 256,
    }

    assert isinstance(error_mw, StubErrorHandlingMiddleware)
    assert error_mw.kwargs == {
        "include_traceback": True,
        "transform_errors": False,
    }

    assert isinstance(retry_mw, StubRetryMiddleware)
    assert retry_mw.kwargs == {
        "max_retries": 4,
        "base_delay": pytest.approx(0.25),
        "max_delay": pytest.approx(5.0),
        "backoff_multiplier": pytest.approx(3.0),
    }

    assert mcp.transport == "streamable-http"


def test_app_adds_caching_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POWERSEARCH_CACHE", "memory")
    monkeypatch.setenv("POWERSEARCH_CACHE_TTL_SEC", "1800")

    monkeypatch.setattr("fastmcp.server.FastMCP", StubMCP)
    monkeypatch.setattr(
        "fastmcp.server.middleware.logging.LoggingMiddleware",
        StubLoggingMiddleware,
    )
    monkeypatch.setattr(
        "fastmcp.server.middleware.error_handling.ErrorHandlingMiddleware",
        StubErrorHandlingMiddleware,
    )
    monkeypatch.setattr(
        "fastmcp.server.middleware.error_handling.RetryMiddleware",
        StubRetryMiddleware,
    )

    monkeypatch.setattr(
        "fastmcp.server.middleware.caching.ResponseCachingMiddleware",
        StubResponseCachingMiddleware,
    )

    settings_module = importlib.import_module("powersearch_mcp.settings")
    importlib.reload(settings_module)

    app_module = importlib.import_module("powersearch_mcp.app")
    importlib.reload(app_module)

    mcp = app_module.mcp

    assert isinstance(mcp, StubMCP)
    assert len(mcp.added) == 4

    caching_mw = mcp.added[-1]
    assert isinstance(caching_mw, StubResponseCachingMiddleware)
    assert caching_mw.kwargs == {
        "cache_storage": ANY,
        "call_tool_settings": {
            "enabled": True,
            "ttl": 1800,
            "included_tools": ["search", "fetch_url"],
        },
    }
    assert isinstance(caching_mw.kwargs["cache_storage"], MemoryStore)


def test_app_adds_eunomia_when_policy_configured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        """
{
  "version": "1.0",
  "name": "test-policy",
  "rules": [],
  "default_effect": "deny"
}
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("POWERSEARCH_AUTHZ_POLICY_PATH", str(policy_path))

    monkeypatch.setattr("fastmcp.server.FastMCP", StubMCP)
    monkeypatch.setattr(
        "fastmcp.server.middleware.logging.LoggingMiddleware",
        StubLoggingMiddleware,
    )
    monkeypatch.setattr(
        "fastmcp.server.middleware.error_handling.ErrorHandlingMiddleware",
        StubErrorHandlingMiddleware,
    )
    monkeypatch.setattr(
        "fastmcp.server.middleware.error_handling.RetryMiddleware",
        StubRetryMiddleware,
    )

    monkeypatch.setattr(
        "eunomia_mcp.create_eunomia_middleware",
        lambda *, policy_file, enable_audit_logging: StubEunomiaMiddleware(
            policy_file=policy_file,
            enable_audit_logging=enable_audit_logging,
        ),
    )

    settings_module = importlib.import_module("powersearch_mcp.settings")
    importlib.reload(settings_module)

    app_module = importlib.import_module("powersearch_mcp.app")
    importlib.reload(app_module)

    mcp = app_module.mcp

    assert isinstance(mcp, StubMCP)
    assert len(mcp.added) == 4

    eunomia_mw = mcp.added[-1]
    assert isinstance(eunomia_mw, StubEunomiaMiddleware)
    assert eunomia_mw.kwargs == {
        "policy_file": str(policy_path),
        "enable_audit_logging": True,
    }


def test_app_fails_when_policy_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    missing = Path("/nonexistent/policy.json")
    monkeypatch.setenv("POWERSEARCH_AUTHZ_POLICY_PATH", str(missing))

    monkeypatch.setattr("fastmcp.server.FastMCP", StubMCP)
    monkeypatch.setattr(
        "fastmcp.server.middleware.logging.LoggingMiddleware",
        StubLoggingMiddleware,
    )
    monkeypatch.setattr(
        "fastmcp.server.middleware.error_handling.ErrorHandlingMiddleware",
        StubErrorHandlingMiddleware,
    )
    monkeypatch.setattr(
        "fastmcp.server.middleware.error_handling.RetryMiddleware",
        StubRetryMiddleware,
    )

    settings_module = importlib.import_module("powersearch_mcp.settings")
    importlib.reload(settings_module)

    with pytest.raises((RuntimeError, FileNotFoundError)):
        app_module = importlib.import_module("powersearch_mcp.app")
        importlib.reload(app_module)

    monkeypatch.delenv("POWERSEARCH_AUTHZ_POLICY_PATH", raising=False)
