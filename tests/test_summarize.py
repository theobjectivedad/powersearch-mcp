import json
from collections.abc import Sequence
from types import SimpleNamespace
from typing import TypedDict, cast

import pytest
from fastmcp.server import Context

from powersearch_mcp import summarize
from powersearch_mcp.powersearch import SearchResultRecord
from powersearch_mcp.settings import powersearch_settings as settings


class SampleCall(TypedDict):
    messages: str | Sequence[object]
    kwargs: dict[str, object | None]


class StubCtx:
    def __init__(self, sample_texts: list[str]) -> None:
        self.sample_texts = sample_texts
        self.sample_calls: list[SampleCall] = []
        self.progress: list[tuple[int, int, str | None]] = []
        self.warnings: list[str] = []

    async def sample(
        self,
        messages: str | Sequence[object],
        *,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        model_preferences: object | None = None,
        tools: object | None = None,
        result_type: type[object] | None = None,
        mask_error_details: bool | None = None,
    ) -> SimpleNamespace:  # noqa: D401
        self.sample_calls.append(
            {
                "messages": messages,
                "kwargs": {
                    "system_prompt": system_prompt,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "model_preferences": model_preferences,
                    "tools": tools,
                    "result_type": result_type,
                    "mask_error_details": mask_error_details,
                },
            }
        )
        text = self.sample_texts.pop(0) if self.sample_texts else ""
        return SimpleNamespace(text=text)

    async def report_progress(
        self, *, progress: int, total: int, message: str | None = None
    ) -> None:  # noqa: D401 - simple recorder
        self.progress.append((progress, total, message))

    async def warning(self, message: str) -> None:  # noqa: D401 - simple recorder
        self.warnings.append(message)

    async def info(
        self, message: str
    ) -> None:  # pragma: no cover - unused in tests
        return None

    async def error(
        self, message: str
    ) -> None:  # pragma: no cover - unused in tests
        self.warnings.append(message)


def _fake_results(count: int = 2) -> list[SearchResultRecord]:
    return [
        SearchResultRecord(
            title=f"Title {idx}",
            url=f"http://example.com/{idx}",
            content=f"Body {idx} " * 10,
        )
        for idx in range(count)
    ]


@pytest.mark.asyncio
async def test_single_pass_summary(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = StubCtx(["summarized"])

    async def fake_search(**_: object) -> list[SearchResultRecord]:
        return _fake_results()

    monkeypatch.setattr(summarize, "search", fake_search)

    result = await summarize.summarize_search_results(
        cast(Context, ctx),
        query="q",
        intent="intent",
        map_reduce=False,
    )

    assert result.summary == "summarized"
    assert len(ctx.sample_calls) == 1
    assert result.sources


@pytest.mark.asyncio
async def test_map_reduce_runs_multiple_sampling_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = StubCtx(["chunk1", "chunk2", "final"])

    async def fake_search(**_: object) -> list[SearchResultRecord]:
        return _fake_results(2)

    monkeypatch.setattr(summarize, "search", fake_search)
    monkeypatch.setattr(settings, "summary_chunk_size", 1)

    result = await summarize.summarize_search_results(
        cast(Context, ctx),
        query="q",
        intent="intent",
        map_reduce=True,
    )

    assert len(ctx.sample_calls) == 3
    assert result.summary == "final"
    assert result.sources


@pytest.mark.asyncio
async def test_no_results_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = StubCtx([])

    async def fake_search(**_: object) -> list[SearchResultRecord]:
        return []

    monkeypatch.setattr(summarize, "search", fake_search)

    result = await summarize.summarize_search_results(
        cast(Context, ctx),
        query="q",
        intent="intent",
    )

    assert result.summary == ""
    assert result.sources == []
    assert ctx.warnings


@pytest.mark.asyncio
async def test_summary_content_limit_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = StubCtx(["summarized"])
    long_content = "abcdefghij"

    async def fake_search(**_: object) -> list[SearchResultRecord]:
        return [
            SearchResultRecord(
                title="Long",
                url="http://example.com/long",
                content=long_content,
            )
        ]

    monkeypatch.setattr(summarize, "search", fake_search)
    monkeypatch.setattr(settings, "summary_content_limit", 5)

    result = await summarize.summarize_search_results(
        cast(Context, ctx),
        query="q",
        intent="intent",
        map_reduce=False,
    )

    prompt = ctx.sample_calls[0]["messages"]
    assert isinstance(prompt, str)
    _, json_block = prompt.split("\n\n", maxsplit=1)
    rendered_results = json.loads(json_block)["search-results"]

    assert rendered_results[0]["content"] == long_content[:5]
    assert result.summary == "summarized"
    assert result.sources == ["http://example.com/long"]
