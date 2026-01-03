"""ASGI app factory and MCP wiring for PowerSearch."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

from fastmcp.client.sampling.handlers.openai import OpenAISamplingHandler
from fastmcp.server import Context, FastMCP
from fastmcp.server.middleware.caching import ResponseCachingMiddleware
from fastmcp.server.middleware.error_handling import (
    ErrorHandlingMiddleware,
    RetryMiddleware,
)
from fastmcp.server.middleware.logging import LoggingMiddleware
from mcp.types import (
    ClientCapabilities,
    SamplingCapability,
    SamplingToolsCapability,
)
from openai import AsyncOpenAI
from pydantic import Field
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from starlette.applications import Starlette
    from starlette.requests import Request
else:
    Starlette = object
    Request = object


from powersearch_mcp import __version__
from powersearch_mcp.powersearch import SearchResultRecord
from powersearch_mcp.powersearch import fetch_url as run_fetch_url
from powersearch_mcp.powersearch import search as run_search
from powersearch_mcp.settings import (
    build_key_value_store,
    server_settings,
)
from powersearch_mcp.summarize import SearchSummary
from powersearch_mcp.summarize import (
    summarize_search_results as run_summarize_search,
)

logger = logging.getLogger(__name__)


sampling_handler = None

if server_settings.openai_api_key and server_settings.openai_default_model:
    client = (
        AsyncOpenAI(
            api_key=server_settings.openai_api_key,
            base_url=str(server_settings.openai_base_url),
        )
        if server_settings.openai_base_url
        else AsyncOpenAI(api_key=server_settings.openai_api_key)
    )

    sampling_handler = OpenAISamplingHandler(
        default_model=server_settings.openai_default_model,  # type: ignore
        client=client,
    )
elif server_settings.fallback_behavior:
    logger.warning(
        "Sampling fallback behavior configured without sampling handler; ignoring."
    )

sampling_handler_behavior = (
    server_settings.fallback_behavior if sampling_handler else None
)

mcp = FastMCP(
    name="powersearch-mcp",
    instructions=(
        "Internet search plus page fetch and sampling-based summarization. "
        "search(query, time_range=day|month|year) returns results with title, url, and "
        "cleaned markdown content. fetch_url(url, fetch_timeout_ms) fetches a single page "
        "and returns cleaned markdown. summarize_search(query, intent, time_range, map_reduce) "
        "runs a background task that summarizes the search results with citations. Use for public web lookups; do not expect internal data."
    ),
    version=__version__,
    tasks=True,
    sampling_handler=sampling_handler,
    sampling_handler_behavior=sampling_handler_behavior,
)


mcp.add_middleware(
    LoggingMiddleware(
        log_level=server_settings.log_level_value(),
        include_payloads=server_settings.log_payloads,
        include_payload_length=True,
        estimate_payload_tokens=server_settings.log_estimate_tokens,
        max_payload_length=server_settings.log_max_payload_length,
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

if server_settings.authz_policy_path:
    policy_path = Path(server_settings.authz_policy_path).expanduser()

    if not policy_path.is_file():
        message = f"Eunomia policy file not found at {policy_path}"
        logger.error(message)
        raise FileNotFoundError(message)

    from powersearch_mcp.authorization_middleware import factory

    mcp.add_middleware(factory(policy_file=str(policy_path)))


@mcp.prompt(title="Internet Search")
# tasks=True requires async prompts/tools even when no awaits are used.
async def internet_search_prompt(
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


@mcp.prompt(title="Summarize Internet Search")
async def summarize_internet_search_prompt(
    goal: Annotated[str, Field(description="What you are trying to find")],
    intent: Annotated[
        str,
        Field(
            description="How the agent plans to use the summary (tone, focus, depth)"
        ),
    ],
    time_range: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional recency bias: day, month, or year.",
        ),
    ] = None,
) -> str:
    recency_hint = (
        f" Include time_range='{time_range}' if you need recent results."
        if time_range
        else ""
    )

    return (
        "You can summarize public web results via the powersearch MCP server.\n"
        f"Goal: {goal}\n"
        f"Intent: {intent}\n"
        f"- Call powersearch/summarize_search with the goal as the query and the intent as guidance.{recency_hint}\n"
        "- By default it uses a single-pass summary; set map_reduce=true for larger corpora knowing sampling is sequential.\n"
        "- Cite URLs from the results; do not invent sources or facts."
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


@mcp.tool(task=True)
async def summarize_search(  # noqa: PLR0913
    ctx: Context,
    query: Annotated[
        str, Field(description="Search query string to summarize")
    ],
    intent: Annotated[
        str,
        Field(
            description="Agent intent that shapes the summary tone and focus"
        ),
    ],
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
    max_results: Annotated[
        int | None,
        Field(
            default=None,
            ge=1,
            description="Optional cap on results included in the summary context.",
        ),
    ] = None,
    map_reduce: Annotated[
        bool | None,
        Field(
            default=None,
            description=(
                "Use sequential map-reduce summarization to handle more results; slower but more thorough."
            ),
        ),
    ] = None,
) -> SearchSummary:
    """Summarize search results via MCP sampling with citations preserved."""

    has_sampling = ctx.session.check_client_capability(
        capability=ClientCapabilities(sampling=SamplingCapability())
    )
    has_tools_capability = ctx.session.check_client_capability(
        capability=ClientCapabilities(
            sampling=SamplingCapability(tools=SamplingToolsCapability())
        )
    )

    if sampling_handler is None and (
        not has_sampling or not has_tools_capability
    ):
        raise RuntimeError(
            "Client does not support sampling capabilities required for summarization."
        )

    map_reduce_flag = bool(map_reduce)

    return await run_summarize_search(
        ctx=ctx,
        query=query,
        intent=intent,
        time_range=time_range,
        max_results=max_results,
        map_reduce=map_reduce_flag,
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
