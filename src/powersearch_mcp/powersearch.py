"""Core PowerSearch search and fetch logic decoupled from MCP wiring."""

import asyncio
import logging
import re
import time
from typing import Any, Protocol
from urllib.parse import urljoin

import httpx
import numpy as np
import trafilatura
from pydantic import BaseModel, Field
from scrapling.fetchers import StealthyFetcher
from trafilatura.settings import use_config

from powersearch_mcp.settings import powersearch_settings as settings

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

HTTP_STATUS_OK_MIN = 200
HTTP_STATUS_OK_MAX = 299
VALID_TIME_RANGES = {"day", "month", "year"}


class MessageSink(Protocol):
    async def info(self, message: str) -> None: ...

    async def warning(self, message: str) -> None: ...

    async def error(self, message: str) -> None: ...


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
                # Insight - I would love to do MCP progress reporting here.
                # However, since we're doing async I/O, it adds too much
                # unwanted complexity.
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
            disable_resources=True,
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

    if markdown_content:
        markdown_content = markdown_content.strip()
    else:
        if ctx:
            await ctx.error(f"No content extracted from {url}")
        markdown_content = ""

    markdown_content = re.sub(r"<[^>]+>", "", markdown_content)
    markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content)
    markdown_content = re.sub(
        r"```\s*```",
        "",
        markdown_content,
    )

    if settings.content_limit is not None:
        markdown_content = markdown_content[: settings.content_limit]

    return markdown_content


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
    "SearchError",
    "SearchResultRecord",
    "StealthyFetcher",
    "_filter_scores_by_percentile",
    "_filter_scores_by_top_k",
    "fetch_url",
    "search",
    "settings",
]
