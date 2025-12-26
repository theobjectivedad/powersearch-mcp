import json
import logging
from collections.abc import Iterator
from typing import Any

import pytest
from click.testing import CliRunner
from starlette.testclient import TestClient

from powersearch_mcp.__main__ import cli
from powersearch_mcp.app import app, create_app, mcp
from powersearch_mcp.http_server import run_http
from powersearch_mcp.powersearch import settings

# ruff: noqa: S101, S104, PLR2004


@pytest.fixture(scope="module")
def http_client() -> Iterator[TestClient]:
    """Shared HTTP client so the streamable session manager only starts once."""

    with TestClient(
        create_app(),
        base_url="http://localhost:8000",
    ) as client:
        yield client


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
    captured: dict[str, Any] = {}

    def fake_uvicorn_run(
        app: object, host: str, port: int, **kwargs: object
    ) -> None:
        captured["app"] = app
        captured["host"] = host
        captured["port"] = port
        captured["kwargs"] = kwargs

    monkeypatch.setattr(
        "powersearch_mcp.http_server.uvicorn.run", fake_uvicorn_run
    )

    cli.main(
        args=[
            "--transport",
            "http",
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
        ],
        standalone_mode=False,
    )

    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 9000
    assert captured["kwargs"]["log_level"] == "info"
    assert captured["app"] is not None


def test_cli_reads_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    monkeypatch.setenv("POWERSEARCH_HTTP_HOST", "1.2.3.4")
    monkeypatch.setenv("POWERSEARCH_HTTP_PORT", "9123")
    monkeypatch.setenv("POWERSEARCH_HTTP_LOG_LEVEL", "debug")

    def fake_uvicorn_run(
        app: object, host: str, port: int, **kwargs: object
    ) -> None:
        captured["app"] = app
        captured["host"] = host
        captured["port"] = port
        captured["kwargs"] = kwargs

    monkeypatch.setattr(
        "powersearch_mcp.http_server.uvicorn.run", fake_uvicorn_run
    )

    cli.main(args=["--transport", "http"], standalone_mode=False)
    assert captured["host"] == "1.2.3.4"
    assert captured["port"] == 9123
    assert captured["kwargs"]["log_level"] == "debug"
    assert captured["app"] is not None


def test_health_route_is_exposed(http_client: TestClient) -> None:
    response = http_client.get("/health")

    assert response.status_code == 200
    assert response.text == ""


def test_options_route_is_exposed(http_client: TestClient) -> None:
    response = http_client.options(
        "/mcp",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code in {200, 204}
    assert response.headers["Access-Control-Allow-Origin"] == "*"
    assert "OPTIONS" in response.headers["Access-Control-Allow-Methods"]
    assert "POST" in response.headers["Access-Control-Allow-Methods"]
    assert "Content-Type" in response.headers["Access-Control-Allow-Headers"]
