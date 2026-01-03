from types import SimpleNamespace

import pytest

from powersearch_mcp import summarize
from powersearch_mcp.powersearch import SearchResultRecord
from powersearch_mcp.settings import powersearch_settings as settings


class StubCtx:
    def __init__(self, sample_texts: list[str]) -> None:
        self.sample_texts = sample_texts
        self.sample_calls: list[dict[str, object]] = []
        self.progress: list[tuple[int, int, str | None]] = []
        self.warnings: list[str] = []

    async def sample(self, *args: object, **kwargs: object) -> SimpleNamespace:  # noqa: D401
        self.sample_calls.append({"args": args, "kwargs": kwargs})
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
        ctx,
        query="q",
        intent="intent",
        map_reduce=False,
    )

    assert result.summary == "summarized"
    assert result.strategy == "single-pass"
    assert len(ctx.sample_calls) == 1
    assert result.citations


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
        ctx,
        query="q",
        intent="intent",
        map_reduce=True,
    )

    assert result.strategy == "map-reduce"
    assert len(ctx.sample_calls) == 3
    assert result.summary == "final"


@pytest.mark.asyncio
async def test_no_results_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = StubCtx([])

    async def fake_search(**_: object) -> list[SearchResultRecord]:
        return []

    monkeypatch.setattr(summarize, "search", fake_search)

    result = await summarize.summarize_search_results(
        ctx,
        query="q",
        intent="intent",
    )

    assert result.summary == ""
    assert result.citations == []
    assert result.results == []
    assert ctx.warnings
