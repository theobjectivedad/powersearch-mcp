"""Sampling-driven search result summarization for PowerSearch."""

from __future__ import annotations

from typing import Iterable, Sequence

from fastmcp.server import Context
from pydantic import BaseModel, Field

from powersearch_mcp.powersearch import SearchResultRecord, search
from powersearch_mcp.settings import powersearch_settings as settings

SYSTEM_PROMPT = (
    "You summarize web search results for an AI agent. "
    "Preserve factual accuracy, keep citations as URLs, "
    "and prefer concise, actionable language. If sources disagree, call that out. "
    "Do not invent facts or sources."
)


class SearchSummary(BaseModel):
    """Structured summary payload returned to MCP clients."""

    summary: str = Field(description="Concise summary of the search results.")
    citations: list[str] = Field(
        default_factory=list,
        description="URLs referenced in the summary for citation and follow-up.",
    )
    strategy: str = Field(
        description="Summarization strategy used: single-pass or map-reduce.",
    )
    results: list[SearchResultRecord] = Field(
        default_factory=list,
        description="Trimmed search results included in the summary context.",
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
    """Render results into a text block for the sampling prompt."""

    lines: list[str] = []
    for idx, result in enumerate(results, start=1):
        lines.append(f"Result {idx}: {result.title}\nURL: {result.url}")
        if result.content:
            lines.append("Content:\n" + result.content)
        lines.append("")
    return "\n".join(lines).strip()


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
    sampling_result = await ctx.sample(
        user_prompt,
        system_prompt=SYSTEM_PROMPT,
        temperature=settings.summary_temperature,
        max_tokens=settings.summary_max_tokens,
    )
    text = getattr(sampling_result, "text", None)
    if text is None:
        return str(sampling_result)
    return text


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
        "Summarize the search results below. Keep citations as URLs.\n\n"
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
            "Summarize this subset of search results. Keep citations as URLs.\n\n"
            f"{_render_results(chunk)}"
        )
        chunk_summary = await _run_sampling(ctx, user_prompt=chunk_prompt)
        chunk_summaries.append(chunk_summary)

    combined_prompt = (
        f"Query: {query}\n"
        f"Intent: {intent}\n"
        "Combine the partial summaries into a single concise answer. Keep citations as URLs.\n\n"
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
            citations=[],
            strategy="single-pass",
            results=[],
        )

    capped_results = _trim_results(
        search_results,
        max_results=max_results or settings.filter_top_k,
        content_limit=settings.content_limit,
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
        strategy = "map-reduce"
    else:
        summary_text = await _single_pass_summary(
            ctx,
            query=query,
            intent=intent,
            results=capped_results,
        )
        strategy = "single-pass"

    await ctx.report_progress(
        progress=100, total=100, message="Summary complete"
    )

    return SearchSummary(
        summary=summary_text.strip(),
        citations=[result.url for result in capped_results],
        strategy=strategy,
        results=capped_results,
    )


__all__ = [
    "SearchSummary",
    "summarize_search_results",
]
