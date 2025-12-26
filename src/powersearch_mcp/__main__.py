"""CLI entrypoint for PowerSearch MCP in stdio or HTTP modes."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Annotated, cast

import click
import uvicorn
from mcp.server.fastmcp import Context, FastMCP
from pydantic import Field
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from collections.abc import Callable

    from mcp.server.session import ServerSessionT
    from mcp.shared.context import LifespanContextT
    from starlette.applications import Starlette
    from starlette.requests import Request
else:  # pragma: no cover - runtime aliases for annotation evaluation
    ServerSessionT = object
    LifespanContextT = object
    Starlette = object
    Request = object

from .powersearch import SearchResultRecord
from .powersearch import fetch_url as run_fetch_url
from .powersearch import search as run_search

DEFAULT_HOST = os.getenv("POWERSEARCH_HTTP_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("POWERSEARCH_HTTP_PORT", "8000"))
DEFAULT_PATH = os.getenv("POWERSEARCH_HTTP_PATH", "/mcp")
DEFAULT_LOG_LEVEL = os.getenv("POWERSEARCH_HTTP_LOG_LEVEL", "info")

mcp = FastMCP(
    name="powersearch",
    instructions=(
        "Internet search plus page fetch. "
        "search(query, time_range=day|month|year) returns results with title, url, and "
        "cleaned markdown content. fetch_url(url, fetch_timeout_ms) fetches a single page "
        "and returns cleaned markdown. Use for public web lookups; do not expect internal data."
    ),
)


@mcp.prompt(title="Internet Search")
def internet_search_prompt(
    goal: Annotated[str, Field(description="What you are trying to find")],
    time_range: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional recency bias: day, month, or year.",
        ),
    ] = None,
) -> str:
    """Lightweight prompt for agents to run a web lookup with powersearch tools."""

    recency_hint = (
        f" Include time_range='{time_range}' if you need recent results."
        if time_range
        else ""
    )

    return (
        "You can search the public web via the powersearch MCP server.\n"
        f"Goal: {goal}\n"
        f"- Call powersearch/search with the goal as the query.{recency_hint}\n"
        "- Results include cleaned content; call fetch_url only to refresh a specific URL.\n"
        "- Summarize briefly and cite URLs; do not invent sources."
    )


@mcp.tool()
async def search(
    ctx: Context[ServerSessionT, LifespanContextT],
    query: Annotated[str, Field(description="Search query string")],
    time_range: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Restrict results to a timeframe: day, month, or year. "
                "Leave empty to search all time."
            ),
        ),
    ] = None,
) -> list[SearchResultRecord]:
    """MCP tool wrapper for the core search implementation."""

    return await run_search(ctx=ctx, query=query, time_range=time_range)


@mcp.tool()
async def fetch_url(
    ctx: Context[ServerSessionT, LifespanContextT],
    url: Annotated[
        str, Field(..., description="URL to fetch from the Internet")
    ],
    fetch_timeout_ms: Annotated[
        int,
        Field(
            default=10 * 1000,
            description=(
                "Per-request timeout in milliseconds applied to the upstream fetch."
            ),
        ),
    ] = 10 * 1000,
) -> str:
    """MCP tool wrapper for fetching and cleaning URL content."""

    return await run_fetch_url(
        ctx=ctx,
        url=url,
        fetch_timeout_ms=fetch_timeout_ms,
    )


async def _health_check(_request: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy", "service": "powersearch-mcp"})


health_check = cast(
    "Callable[[Request], JSONResponse]",
    mcp.custom_route("/health", methods=["GET"])(_health_check),
)


def _normalize_path(path: str) -> str:
    """Ensure the HTTP path is rooted and not empty."""

    normalized = (path or "").strip() or "/mcp"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized.rstrip("/") or "/"


def create_http_app(path: str) -> Starlette:
    """Return an ASGI app for the Streamable HTTP transport."""

    normalized_path = _normalize_path(path)
    mcp.settings.streamable_http_path = normalized_path
    return mcp.streamable_http_app()


def run_stdio() -> None:
    """Start the MCP server over stdio (default)."""

    mcp.run(transport="stdio")


def run_http(  # noqa: PLR0913
    *,
    host: str,
    port: int,
    path: str,
    log_level: str,
    ssl_certfile: str | None,
    ssl_keyfile: str | None,
    ssl_keyfile_password: str | None,
    ssl_ca_certs: str | None,
    reload: bool,
) -> None:
    """Start the MCP server as an ASGI app under uvicorn."""

    app = create_http_app(path)

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level.lower(),
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        ssl_keyfile_password=ssl_keyfile_password,
        ssl_ca_certs=ssl_ca_certs,
        reload=reload,
    )


@click.command()
@click.option(
    "--transport",
    type=click.Choice(["stdio", "http"], case_sensitive=False),
    default="stdio",
    show_default=True,
    help="Transport to launch (stdio or HTTP).",
)
@click.option(
    "--host",
    default=DEFAULT_HOST,
    show_default=True,
    envvar="POWERSEARCH_HTTP_HOST",
    help="Host interface for HTTP transport.",
)
@click.option(
    "--port",
    type=int,
    default=DEFAULT_PORT,
    show_default=True,
    envvar="POWERSEARCH_HTTP_PORT",
    help="Port for HTTP transport.",
)
@click.option(
    "--path",
    default=DEFAULT_PATH,
    show_default=True,
    envvar="POWERSEARCH_HTTP_PATH",
    help="Request path for the HTTP transport (default /mcp).",
)
@click.option(
    "--log-level",
    default=DEFAULT_LOG_LEVEL,
    show_default=True,
    envvar="POWERSEARCH_HTTP_LOG_LEVEL",
    type=click.Choice(
        ["critical", "error", "warning", "info", "debug", "trace"],
        case_sensitive=False,
    ),
    help="Log level for uvicorn in HTTP mode.",
)
@click.option(
    "--ssl-certfile",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    envvar="POWERSEARCH_HTTP_SSL_CERTFILE",
    help="PEM-encoded certificate file to enable HTTPS.",
)
@click.option(
    "--ssl-keyfile",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    envvar="POWERSEARCH_HTTP_SSL_KEYFILE",
    help="PEM-encoded private key file to enable HTTPS.",
)
@click.option(
    "--ssl-keyfile-password",
    envvar="POWERSEARCH_HTTP_SSL_KEYFILE_PASSWORD",
    help="Password for the TLS private key, if encrypted.",
)
@click.option(
    "--ssl-ca-certs",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    envvar="POWERSEARCH_HTTP_SSL_CA_CERTS",
    help="Optional CA bundle for client verification.",
)
@click.option(
    "--reload/--no-reload",
    default=False,
    show_default=True,
    envvar="POWERSEARCH_HTTP_RELOAD",
    help="Enable uvicorn reload (development only).",
)
def cli(  # noqa: PLR0913
    *,
    transport: str,
    host: str,
    port: int,
    path: str,
    log_level: str,
    ssl_certfile: str | None,
    ssl_keyfile: str | None,
    ssl_keyfile_password: str | None,
    ssl_ca_certs: str | None,
    reload: bool,
) -> None:
    """Launch PowerSearch MCP over stdio or HTTP."""

    if (ssl_certfile and not ssl_keyfile) or (ssl_keyfile and not ssl_certfile):
        msg = "Both --ssl-certfile and --ssl-keyfile are required to enable HTTPS."
        raise click.BadParameter(msg)

    transport_choice = transport.lower()

    if transport_choice == "stdio":
        run_stdio()
        return

    run_http(
        host=host,
        port=port,
        path=path,
        log_level=log_level,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        ssl_keyfile_password=ssl_keyfile_password,
        ssl_ca_certs=ssl_ca_certs,
        reload=reload,
    )


def main() -> None:
    cli(standalone_mode=True)


if __name__ == "__main__":
    main()
