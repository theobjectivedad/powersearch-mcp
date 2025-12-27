from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from powersearch_mcp.app import create_app

ROOT = Path(__file__).resolve().parents[1]
STDIO_CONFIG = ROOT / "fastmcp.json"
HTTP_CONFIG = ROOT / "fastmcp-http.json"

# ruff: noqa: S101, S104, PLR2004


@pytest.fixture(scope="module")
def http_client() -> Iterator[TestClient]:
    """Shared HTTP client so the streamable session manager only starts once."""

    with TestClient(
        create_app(),
        base_url="http://localhost:8000",
    ) as client:
        yield client


def test_stdio_config_defaults() -> None:
    data = json.loads(STDIO_CONFIG.read_text())

    assert data["source"]["path"] == "src/powersearch_mcp/app.py"
    assert data["source"]["entrypoint"] == "mcp"
    assert data["deployment"]["transport"] == "stdio"
    assert data["environment"]["python"] == "3.13"
    deps = data["environment"]["dependencies"]
    for required in (
        "fastmcp>=2.14,<3",
        "httpx[http2]>=0.28.1,<1",
        "uvicorn>=0.40.0,<1",
    ):
        assert required in deps


def test_http_config_defaults() -> None:
    data = json.loads(HTTP_CONFIG.read_text())

    deployment = data["deployment"]
    assert deployment["transport"] == "streamable-http"
    assert deployment["host"] == "0.0.0.0"
    assert deployment["port"] == 8092
    assert deployment["path"] == "/mcp"


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
