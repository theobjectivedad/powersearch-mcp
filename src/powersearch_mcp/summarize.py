"""Sampling-driven search result summarization for PowerSearch."""

from __future__ import annotations

# ruff: noqa: PLR0913
import json
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from powersearch_mcp.powersearch import SearchResultRecord, search
from powersearch_mcp.settings import powersearch_settings as settings

if TYPE_CHECKING:  # pragma: no cover - typing only
    from collections.abc import Iterable, Sequence

    from fastmcp.server import Context

SYSTEM_PROMPT = (
    "You summarize web search results for an AI agent. "
    "Preserve factual accuracy and keep citations as markdown links using the provided URLs. "
    "Prefer concise, actionable language. If sources disagree, call that out. "
    "Do not invent facts or sources."
)

RESULTS_JSON_INSTRUCTION = (
    'Search results are provided as JSON under "search-results", '
    "where each item has fields: result (ordinal), url, and content (markdown)."
)

SUMMARY_INSTRUCTION = (
    "Write a single markdown summary that combines all results. "
    "Use inline markdown citations that link to the provided URLs."
)


class SearchSummary(BaseModel):
    """Structured summary payload returned to MCP clients."""

    summary: str = Field(description="Summary of the search results.")
    sources: list[str] = Field(
        default_factory=list,
        description="URLs cited in the summary.",
    )


def _trim_results(
    results: Sequence[SearchResultRecord],
    *,
    max_results: int,
    content_limit: int | None,
) -> list[SearchResultRecord]:
    """Limit result count and per-result content size for sampling safety."""

    trimmed: list[SearchResultRecord] = []
    for result in results[:max_results]:
        trimmed_content = (
            result.content[:content_limit]
            if content_limit is not None
            else result.content
        )
        trimmed.append(
            SearchResultRecord(
                title=result.title,
                url=result.url,
                content=trimmed_content,
            )
        )
    return trimmed


def _render_results(results: Sequence[SearchResultRecord]) -> str:
    """Render results as structured JSON to delineate each entry."""

    payload: dict[str, list[dict[str, object]]] = {"search-results": []}
    for idx, result in enumerate(results, start=1):
        payload["search-results"].append(
            {
                "result": idx,
                "url": result.url,
                "content": result.content,
            }
        )

    return json.dumps(payload, indent=2, ensure_ascii=True)


def _chunk_results(
    results: Sequence[SearchResultRecord], chunk_size: int
) -> Iterable[list[SearchResultRecord]]:
    for start in range(0, len(results), chunk_size):
        yield list(results[start : start + chunk_size])


async def _run_sampling(
    ctx: Context,
    *,
    user_prompt: str,
) -> str:
    sampling_result: object = await ctx.sample(
        user_prompt,
        system_prompt=SYSTEM_PROMPT,
        temperature=settings.summary_temperature,
        max_tokens=settings.summary_max_tokens,
    )
    result_text = getattr(sampling_result, "text", None)
    if isinstance(result_text, str):
        return result_text
    return str(sampling_result)


async def _single_pass_summary(
    ctx: Context,
    *,
    query: str,
    intent: str,
    results: Sequence[SearchResultRecord],
) -> str:
    user_prompt = (
        f"Query: {query}\n"
        f"Intent: {intent}\n"
        f"{RESULTS_JSON_INSTRUCTION}\n"
        f"{SUMMARY_INSTRUCTION}\n"
        "Summarize the search results below using markdown links for citations.\n\n"
        f"{_render_results(results)}"
    )
    return await _run_sampling(ctx, user_prompt=user_prompt)


async def _map_reduce_summary(
    ctx: Context,
    *,
    query: str,
    intent: str,
    results: Sequence[SearchResultRecord],
) -> str:
    chunk_size = max(1, settings.summary_chunk_size)
    chunks = list(_chunk_results(results, chunk_size))
    chunk_summaries: list[str] = []
    total_chunks = len(chunks)

    for idx, chunk in enumerate(chunks, start=1):
        await ctx.report_progress(
            progress=20 + int((idx - 1) * (60 / max(1, total_chunks))),
            total=100,
            message=f"Summarizing chunk {idx}/{total_chunks}",
        )
        chunk_prompt = (
            f"Query: {query}\n"
            f"Intent: {intent}\n"
            f"{RESULTS_JSON_INSTRUCTION}\n"
            "Summarize this subset of search results as a single markdown answer. "
            "Use inline markdown citations that link to the provided URLs.\n\n"
            f"{_render_results(chunk)}"
        )
        chunk_summary = await _run_sampling(ctx, user_prompt=chunk_prompt)
        chunk_summaries.append(chunk_summary)

    combined_prompt = (
        f"Query: {query}\n"
        f"Intent: {intent}\n"
        f"{SUMMARY_INSTRUCTION}\n"
        "Combine the partial summaries into a single concise markdown answer. "
        "Preserve or re-add markdown citations linking to the search result URLs.\n\n"
        + "\n\n".join(
            f"Chunk {idx}:\n{summary}"
            for idx, summary in enumerate(chunk_summaries, start=1)
        )
    )
    return await _run_sampling(ctx, user_prompt=combined_prompt)


async def summarize_search_results(
    ctx: Context,
    *,
    query: str,
    intent: str,
    time_range: str | None = None,
    max_results: int | None = None,
    map_reduce: bool = False,
) -> SearchSummary:
    """Run a search then summarize it via MCP sampling."""

    await ctx.report_progress(
        progress=0, total=100, message="Searching the web"
    )
    search_results = await search(ctx=ctx, query=query, time_range=time_range)

    if not search_results:
        await ctx.warning("Search returned no results; summary is empty.")
        await ctx.report_progress(progress=100, total=100, message="No results")
        return SearchSummary(
            summary="",
            sources=[],
        )

    capped_results = _trim_results(
        search_results,
        max_results=max_results or settings.filter_top_k,
        content_limit=settings.summary_content_limit,
    )

    await ctx.report_progress(
        progress=15, total=100, message="Summarizing results"
    )

    use_map_reduce = (
        map_reduce and len(capped_results) > settings.summary_chunk_size
    )
    if use_map_reduce:
        summary_text = await _map_reduce_summary(
            ctx,
            query=query,
            intent=intent,
            results=capped_results,
        )
    else:
        summary_text = await _single_pass_summary(
            ctx,
            query=query,
            intent=intent,
            results=capped_results,
        )

    await ctx.report_progress(
        progress=100, total=100, message="Summary complete"
    )

    return SearchSummary(
        summary=summary_text.strip(),
        sources=[result.url for result in capped_results],
    )


__all__ = [
    "SearchSummary",
    "summarize_search_results",
]
