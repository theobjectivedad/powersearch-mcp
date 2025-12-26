"""Core PowerSearch search and fetch logic decoupled from MCP wiring."""

import asyncio
import logging
import re
import time
from typing import Any, Literal, Protocol
from urllib.parse import urljoin

import httpx
import numpy as np
import trafilatura
from pydantic import BaseModel, Field, HttpUrl, TypeAdapter, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from scrapling.fetchers import StealthyFetcher
from trafilatura.settings import use_config

# Logger level configuration
for _logger_name in (
    "httpx",
    "httpcore",
    "scrapling",
    "scrapling.fetchers",
    "scrapling.fetchers.stealthy_fetcher",
    "custom",
):
    logging.getLogger(_logger_name).setLevel(logging.WARNING)

DEFAULT_BASE_URL: HttpUrl = TypeAdapter(HttpUrl).validate_python(
    "http://127.0.0.1:9876"
)
HTTP_STATUS_OK_MIN = 200
HTTP_STATUS_OK_MAX = 299
VALID_TIME_RANGES = {"day", "month", "year"}


class MessageSink(Protocol):
    async def info(self, message: str) -> None: ...

    async def warning(self, message: str) -> None: ...

    async def error(self, message: str) -> None: ...


class PowerSearchSettings(BaseSettings):
    """Runtime configuration for Power Search sourced from environment."""

    model_config = SettingsConfigDict(
        env_prefix="POWERSEARCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: HttpUrl = Field(
        default=DEFAULT_BASE_URL,
        description="Base SearXNG search URL (should end with /search).",
    )
    engines: list[str] = Field(
        default_factory=list,
        description="Comma-separated SearXNG engines to query.",
    )
    language: str = Field(
        default="en",
        description="IETF language tag passed to SearXNG.",
    )
    safe_search: int = Field(
        default=1,
        ge=0,
        le=2,
        description="Safe search level expected by SearXNG (0, 1, or 2).",
    )
    max_page: int = Field(
        default=1,
        ge=1,
        description="Number of result pages to request from SearXNG.",
    )
    filter_score_percentile: float | None = Field(
        default=75.0,
        ge=0,
        le=100,
        description=(
            "Score percentile cutoff; set to None to disable percentile filtering."
        ),
    )
    filter_top_k: int = Field(
        default=10,
        ge=1,
        description="Maximum results retained after filtering by score.",
    )
    content_strategy: Literal["quick", "fetch"] = Field(
        default="fetch",
        description="How to populate result content: quick (use SearXNG snippet) or fetch full pages.",
    )
    content_limit: int | None = Field(
        default=4000,
        ge=0,
        description="Trim each result's content to this many characters; None to disable.",
    )
    timeout_sec: int = Field(
        default=20,
        gt=0,
        description="Total timeout budget (seconds) for search plus content handling.",
    )
    http2: bool = Field(
        default=False,
        description="Enable HTTP/2 for upstream requests when supported.",
    )
    verify: bool = Field(
        default=True,
        description="Verify TLS certificates for upstream requests.",
    )
    trafilatura_extraction_timeout: float = Field(
        default=0.0,
        ge=0,
        description="Seconds trafilatura may spend extracting; 0 disables the limit.",
    )
    trafilatura_min_extracted_size: int = Field(
        default=100,
        ge=0,
        description="Minimum extracted text size required to accept content.",
    )
    trafilatura_min_duplcheck_size: int = Field(
        default=100,
        ge=0,
        description="Minimum size used by trafilatura's duplicate check.",
    )
    trafilatura_max_repetitions: int = Field(
        default=2,
        ge=0,
        description="Maximum repeated content blocks retained before trimming.",
    )
    trafilatura_extensive_date_search: bool = Field(
        default=True,
        description="Enable trafilatura's extensive date search heuristics.",
    )
    trafilatura_include_links: bool = Field(
        default=False,
        description="Whether to include links in extracted markdown.",
    )
    trafilatura_include_images: bool = Field(
        default=False,
        description="Whether to include images in extracted markdown.",
    )
    trafilatura_include_tables: bool = Field(
        default=True,
        description="Whether to include tables in extracted markdown.",
    )
    trafilatura_include_comments: bool = Field(
        default=False,
        description="Whether to include HTML comments in extracted markdown.",
    )
    trafilatura_include_formatting: bool = Field(
        default=False,
        description="Whether to preserve formatting markup from the source.",
    )
    trafilatura_deduplicate: bool = Field(
        default=True,
        description="Deduplicate near-identical blocks while extracting.",
    )
    trafilatura_favor_precision: bool = Field(
        default=True,
        description="Favor precision over recall when extracting content.",
    )

    @field_validator("engines", mode="before")
    @classmethod
    def parse_engines(
        cls, value: str | list[str] | None
    ) -> str | list[str] | None:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("engines")
    @classmethod
    def ensure_engines(cls, value: list[str]) -> list[str]:
        return [engine for engine in value if engine]


settings = PowerSearchSettings()


class SearchResultRecord(BaseModel):
    """Search result record model for PowerSearch."""

    title: str = Field(
        description="Title of the search result",
    )
    url: str = Field(
        description="URL of the search result",
    )
    content: str = Field(
        description="Full content of the search URL",
    )


class FetchError(Exception):
    """Raised when there is an error fetching or converting the URL."""


class SearchError(Exception):
    """Raised when there is an error performing the search."""


def _filter_scores_by_percentile(
    searxng_results: list[dict[str, Any]], percentile: float | None
) -> list[dict[str, Any]]:
    """Filter SearXNG results by score percentile."""

    if not searxng_results:
        return []

    if percentile is None:
        return _filter_scores_by_top_k(
            searxng_results=searxng_results, k=len(searxng_results)
        )

    scores = [x.get("score", 0) for x in searxng_results]

    return [
        searxng_results[i]
        for i in range(len(scores))
        if scores[i] >= np.percentile(scores, percentile)
    ]


def _filter_scores_by_top_k(
    searxng_results: list[dict[str, Any]], k: int
) -> list[dict[str, Any]]:
    """Filter SearXNG results by top K scores."""

    if k >= len(searxng_results):
        top_k_indices = list(range(len(searxng_results)))

    else:
        scores = np.array([x.get("score", 0) for x in searxng_results])
        partial_indices = np.argpartition(scores, -k)[-k:]
        sorted_order = np.argsort(scores[partial_indices])[::-1]
        top_k_indices = partial_indices[sorted_order].tolist()

    return [searxng_results[i] for i in top_k_indices]


async def search(  # noqa: C901, PLR0912, PLR0915
    ctx: MessageSink,
    query: str,
    time_range: str | None = None,
) -> list[SearchResultRecord]:
    """Search the public web and return cleaned, trimmed markdown content per result."""

    start_time = time.perf_counter()

    base_url_str = str(settings.base_url)
    if not base_url_str.endswith("/search"):
        derived_search_url = urljoin(base_url_str, "/search")
    else:
        derived_search_url = base_url_str

    if time_range and time_range not in VALID_TIME_RANGES:
        await ctx.error(
            f"Invalid time_range '{time_range}'. Choose one of {sorted(VALID_TIME_RANGES)}."
        )
        raise SearchError("Invalid time_range parameter")

    search_results: list[SearchResultRecord] = []

    time_budget = settings.timeout_sec - (time.perf_counter() - start_time)
    if time_budget <= 0:
        await ctx.warning(
            "Timeout budget exhausted before issuing search; using minimum timeout"
        )
        time_budget = 0.1

    async with httpx.AsyncClient(
        follow_redirects=True,
        http1=True,
        http2=settings.http2,
        verify=settings.verify,
        timeout=httpx.Timeout(timeout=time_budget),
    ) as client:
        params: dict[str, str | int | float | bool | None] = {
            "q": query,
            "language": settings.language,
            "safesearch": settings.safe_search,
            "max_page": settings.max_page,
            "format": "json",
        }
        if settings.engines:
            params["engines"] = ",".join(settings.engines)

        if time_range:
            params["time_range"] = time_range

        request_started = time.perf_counter()
        try:
            response = await client.get(
                derived_search_url,
                params=params,
            )
            response.raise_for_status()
            response_dict = response.json()
        except (
            httpx.HTTPStatusError
        ) as exc:  # pragma: no cover - exercised in live test
            elapsed = time.perf_counter() - request_started
            status = exc.response.status_code
            await ctx.error(
                f"SearXNG request failed after {elapsed:.2f}s: status="
                f"{status} reason={exc}"
            )
            raise SearchError("Search error: upstream request failed") from exc
        except (
            httpx.HTTPError
        ) as exc:  # pragma: no cover - exercised in live test
            elapsed = time.perf_counter() - request_started
            await ctx.error(
                f"SearXNG request failed after {elapsed:.2f}s: reason={exc}"
            )
            raise SearchError("Search error: upstream request failed") from exc
        except ValueError as exc:
            elapsed = time.perf_counter() - request_started
            await ctx.error(
                f"SearXNG response JSON decode failed after {elapsed:.2f}s: {exc}"
            )
            raise SearchError(
                "Search error: invalid JSON in SearXNG response"
            ) from exc
        if "results" not in response_dict:
            await ctx.error(
                "Search error: 'results' not found in SearXNG response"
            )
            raise SearchError(
                "Search error: 'results' not found in SearXNG response"
            )

        searxng_results = response_dict["results"]

        if not searxng_results:
            await ctx.warning("Search returned zero results")
            return []

        filtered_searxgn_results = _filter_scores_by_percentile(
            searxng_results=searxng_results,
            percentile=settings.filter_score_percentile,
        )
        filtered_searxgn_results = _filter_scores_by_top_k(
            searxng_results=filtered_searxgn_results,
            k=settings.filter_top_k,
        )

        if not filtered_searxgn_results:
            await ctx.warning("Search returned no results after filtering")
            return []

        search_results = [
            SearchResultRecord(
                title=x["title"],
                content=x["content"],
                url=x["url"],
            )
            for x in filtered_searxgn_results
        ]

        if settings.content_strategy == "fetch":
            time_remaining = settings.timeout_sec - (
                time.perf_counter() - start_time
            )
            if time_remaining <= 0:
                await ctx.warning(
                    "No remaining timeout budget; skipping content fetch"
                )
                return search_results

            fetch_timeout_ms = max(1000, int(time_remaining * 1000))
            fetch_tasks = [
                _fetch_url(
                    ctx=ctx,
                    url=result.url,
                    fetch_timeout_ms=fetch_timeout_ms,
                )
                for result in search_results
            ]

            if fetch_tasks:
                markdown_results = await asyncio.gather(
                    *fetch_tasks, return_exceptions=True
                )

                for i, markdown in enumerate(markdown_results):
                    if isinstance(markdown, Exception):
                        await ctx.error(
                            f"Error fetching {search_results[i].url}: "
                            f"{markdown}"
                        )
                    else:
                        search_results[i].content = str(markdown)
        else:
            if settings.content_strategy != "quick":
                await ctx.warning(
                    "Unknown content strategy, defaulting to 'quick'."
                )

            for i, searxgn_result in enumerate(filtered_searxgn_results):
                search_results[i].content = searxgn_result["content"]

    if settings.content_limit is not None:
        for result in search_results:
            if len(result.content) > settings.content_limit:
                result.content = result.content[: settings.content_limit]

    return search_results


async def _fetch_url(
    ctx: MessageSink | None,
    url: str,
    fetch_timeout_ms: int,
) -> str:
    """Shared implementation for the fetch tool with optional context logging."""

    try:
        resp = await StealthyFetcher.async_fetch(
            url=url,
            timeout=fetch_timeout_ms,
            os_randomize=True,
            block_images=True,
        )
    except Exception as exc:  # pragma: no cover - exercised in live test
        if ctx:
            await ctx.error(f"Fetcher failed for {url}: {exc}")
        raise FetchError(f"Failed to fetch {url}: {exc}") from exc

    if resp.status < HTTP_STATUS_OK_MIN or resp.status > HTTP_STATUS_OK_MAX:
        if ctx:
            await ctx.error(f"Fetch for {url} returned status {resp.status}")
        raise FetchError(f"Failed to fetch {url}: {resp.status}")

    config = use_config()
    config.set(
        "DEFAULT",
        "EXTRACTION_TIMEOUT",
        str(settings.trafilatura_extraction_timeout),
    )
    config.set(
        "DEFAULT",
        "MIN_EXTRACTED_SIZE",
        str(settings.trafilatura_min_extracted_size),
    )
    config.set(
        "DEFAULT",
        "MIN_DUPLCHECK_SIZE",
        str(settings.trafilatura_min_duplcheck_size),
    )
    config.set(
        "DEFAULT",
        "MAX_REPETITIONS",
        str(settings.trafilatura_max_repetitions),
    )
    config.set(
        "DEFAULT",
        "EXTENSIVE_DATE_SEARCH",
        "on" if settings.trafilatura_extensive_date_search else "off",
    )

    markdown_content = trafilatura.extract(
        resp.html_content,
        output_format="markdown",
        url=url,
        favor_precision=settings.trafilatura_favor_precision,
        include_links=settings.trafilatura_include_links,
        include_images=settings.trafilatura_include_images,
        include_tables=settings.trafilatura_include_tables,
        include_comments=settings.trafilatura_include_comments,
        include_formatting=settings.trafilatura_include_formatting,
        deduplicate=settings.trafilatura_deduplicate,
        config=config,
    )
    if not markdown_content:
        if ctx:
            await ctx.error(f"No content extracted from {url}")
        raise FetchError(f"No content extracted from {url}")

    markdown_content = re.sub(r"<[^>]+>", "", markdown_content)
    markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content)
    markdown_content = re.sub(
        r"```\s*```",
        "",
        markdown_content,
    )
    return markdown_content.strip()


async def fetch_url(
    ctx: MessageSink,
    url: str,
    fetch_timeout_ms: int = 10 * 1000,
) -> str:
    """Fetch a URL using a stealthy HTTP client and return cleaned markdown."""

    return await _fetch_url(
        ctx=ctx,
        url=url,
        fetch_timeout_ms=fetch_timeout_ms,
    )


__all__ = [
    "FetchError",
    "PowerSearchSettings",
    "SearchError",
    "SearchResultRecord",
    "_filter_scores_by_percentile",
    "_filter_scores_by_top_k",
    "fetch_url",
    "search",
    "settings",
]
