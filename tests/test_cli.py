from collections.abc import Iterator
from typing import Any

import pytest
from click.testing import CliRunner
from starlette.testclient import TestClient

from powersearch_mcp.__main__ import cli, create_http_app, mcp

# ruff: noqa: S101, S104, PLR2004


@pytest.fixture(autouse=True)
def restore_streamable_path() -> Iterator[None]:
    """Keep the MCP HTTP path stable across CLI tests."""

    original_path = mcp.settings.streamable_http_path
    yield
    mcp.settings.streamable_http_path = original_path


def test_cli_runs_stdio(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    captured: dict[str, Any] = {}

    def fake_run(*, transport: str) -> None:
        captured["transport"] = transport

    monkeypatch.setattr(mcp, "run", fake_run)

    result = runner.invoke(cli, ["--transport", "stdio"])

    assert result.exit_code == 0
    assert captured["transport"] == "stdio"


def test_cli_runs_http_with_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    captured: dict[str, Any] = {}

    def fake_uvicorn_run(
        app: object, host: str, port: int, **kwargs: object
    ) -> None:
        captured["app"] = app
        captured["host"] = host
        captured["port"] = port
        captured["kwargs"] = kwargs
        captured["path"] = mcp.settings.streamable_http_path

    monkeypatch.setattr(
        "powersearch_mcp.__main__.uvicorn.run", fake_uvicorn_run
    )

    result = runner.invoke(
        cli,
        [
            "--transport",
            "http",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
            "--path",
            "api",
        ],
    )

    assert result.exit_code == 0
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 9000
    assert captured["path"] == "/api"
    assert captured["kwargs"]["log_level"] == "info"
    assert captured["app"] is not None


def test_health_route_is_exposed() -> None:
    app = create_http_app("/mcp")
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "service": "powersearch-mcp",
    }
