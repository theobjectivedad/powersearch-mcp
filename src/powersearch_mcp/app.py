"""ASGI app factory and MCP wiring for PowerSearch."""

from typing import TYPE_CHECKING, Annotated

from fastmcp.server import Context, FastMCP
from fastmcp.server.middleware.caching import ResponseCachingMiddleware
from fastmcp.server.middleware.error_handling import (
    ErrorHandlingMiddleware,
    RetryMiddleware,
)
from fastmcp.server.middleware.logging import LoggingMiddleware
from pydantic import Field
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from starlette.applications import Starlette
    from starlette.requests import Request
else:
    Starlette = object
    Request = object


from powersearch_mcp.powersearch import SearchResultRecord
from powersearch_mcp.powersearch import fetch_url as run_fetch_url
from powersearch_mcp.powersearch import search as run_search
from powersearch_mcp.settings import build_key_value_store, server_settings

mcp = FastMCP(
    name="powersearch",
    instructions=(
        "Internet search plus page fetch. "
        "search(query, time_range=day|month|year) returns results with title, url, and "
        "cleaned markdown content. fetch_url(url, fetch_timeout_ms) fetches a single page "
        "and returns cleaned markdown. Use for public web lookups; do not expect internal data."
    ),
)

mcp.add_middleware(
    LoggingMiddleware(
        log_level=server_settings.log_level_value(),
        include_payloads=server_settings.include_payloads,
        include_payload_length=server_settings.include_payload_length,
        estimate_payload_tokens=server_settings.estimate_payload_tokens,
        max_payload_length=server_settings.max_payload_length,
    )
)

mcp.add_middleware(
    ErrorHandlingMiddleware(
        include_traceback=server_settings.errorhandling_traceback,
        transform_errors=server_settings.errorhandling_transform,
    )
)

mcp.add_middleware(
    RetryMiddleware(
        max_retries=server_settings.retry_retries,
        base_delay=server_settings.retry_base_delay,
        max_delay=server_settings.retry_max_delay,
        backoff_multiplier=server_settings.retry_backoff_multiplier,
    )
)

cache_storage = build_key_value_store(
    server_settings.cache_storage, default_collection="powersearch"
)

if cache_storage is not None:
    mcp.add_middleware(
        ResponseCachingMiddleware(
            cache_storage=cache_storage,
            call_tool_settings={
                "enabled": True,
                "ttl": server_settings.cache_ttl_sec,
                "included_tools": ["search", "fetch_url"],
            },
        )
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
    ctx: Context,
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
    ctx: Context,
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


@mcp.custom_route("/health", methods=["GET"])
async def health_check(_request: Request) -> Response:
    return Response(status_code=200)


def create_app() -> Starlette:
    # Use the FastMCP helper to build the Streamable HTTP transport app.
    asgi_app: Starlette = mcp.http_app(transport="streamable-http")

    asgi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=[
            "mcp-protocol-version",
            "mcp-session-id",
            "Authorization",
            "Content-Type",
        ],
        expose_headers=["mcp-session-id"],
    )

    return asgi_app


app = create_app()
