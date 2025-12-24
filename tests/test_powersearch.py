from collections.abc import Iterator
from typing import Any

import httpx
import pytest

from powersearch_mcp.powersearch import (
    FetchError,
    SearchError,
    _filter_scores_by_percentile,
    _filter_scores_by_top_k,
    fetch_url,
    search,
    settings,
)

HTTP_OK_MIN = 200
HTTP_OK_MAX = 299


class DummyCtx:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    async def info(self, message: str) -> None:
        self.messages.append(("info", message))

    async def warning(self, message: str) -> None:
        self.messages.append(("warning", message))

    async def error(self, message: str) -> None:
        self.messages.append(("error", message))


class StubAsyncResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class StubAsyncClient:
    def __init__(self, response: StubAsyncResponse) -> None:
        self._response = response

    async def __aenter__(self) -> "StubAsyncClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def get(self, _url: str, **_: object) -> StubAsyncResponse:
        return self._response


class StubFetcherResponse:
    def __init__(self, html_content: str, status: int = 200) -> None:
        self.html_content = html_content
        self.status = status


@pytest.fixture(autouse=True)
def restore_settings() -> Iterator[None]:
    """Preserve global settings across tests."""

    snapshot = {
        "base_url": settings.base_url,
        "engines": list(settings.engines),
        "language": settings.language,
        "safe_search": settings.safe_search,
        "max_page": settings.max_page,
        "filter_score_percentile": settings.filter_score_percentile,
        "filter_top_k": settings.filter_top_k,
        "content_strategy": settings.content_strategy,
        "content_limit": settings.content_limit,
        "timeout_sec": settings.timeout_sec,
        "http2": settings.http2,
        "verify": settings.verify,
    }
    yield
    for key, value in snapshot.items():
        setattr(settings, key, value)


@pytest.mark.asyncio
async def test_search_fetches_and_trims_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = DummyCtx()
    settings.filter_score_percentile = None
    settings.filter_top_k = 5
    settings.content_strategy = "fetch"
    settings.content_limit = 20

    payload = {
        "results": [
            {
                "title": "Result One",
                "content": "Snippet One",
                "url": "https://example.com/one",
                "score": 10,
            },
            {
                "title": "Result Two",
                "content": "Snippet Two",
                "url": "https://example.com/two",
                "score": 9,
            },
        ]
    }

    stub_response = StubAsyncResponse(payload=payload)
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **_: StubAsyncClient(stub_response)
    )

    async def stub_async_fetch(
        *args: object, **kwargs: object
    ) -> StubFetcherResponse:
        return StubFetcherResponse(html_content="<p>Mock content body</p>")

    monkeypatch.setattr(
        "powersearch_mcp.powersearch.StealthyFetcher.async_fetch",
        stub_async_fetch,
    )
    monkeypatch.setattr(
        "powersearch_mcp.powersearch.trafilatura.extract",
        lambda *_, **__: "Cleaned markdown content with extras",
    )

    results = await search(ctx=ctx, query="query", time_range=None)

    assert len(results) == len(payload["results"])
    for record in results:
        assert isinstance(record.content, str)
        assert len(record.content) <= settings.content_limit

    assert any(level == "info" for level, _ in ctx.messages)


@pytest.mark.asyncio
async def test_fetch_url_raises_on_bad_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = DummyCtx()

    async def stub_async_fetch(
        *args: object, **kwargs: object
    ) -> StubFetcherResponse:
        return StubFetcherResponse(html_content="<p>bad</p>", status=500)

    monkeypatch.setattr(
        "powersearch_mcp.powersearch.StealthyFetcher.async_fetch",
        stub_async_fetch,
    )

    with pytest.raises(FetchError):
        await fetch_url(
            ctx=ctx, url="https://example.com/fail", fetch_timeout_ms=1000
        )

    assert (
        "error",
        "Fetch for https://example.com/fail returned status 500",
    ) in ctx.messages


@pytest.mark.asyncio
async def test_search_rejects_invalid_time_range() -> None:
    ctx = DummyCtx()
    with pytest.raises(SearchError):
        await search(ctx=ctx, query="irrelevant", time_range="week")

    assert (
        "error",
        "Invalid time_range 'week'. Choose one of ['day', 'month', 'year'].",
    ) in ctx.messages


def test_filter_score_helpers_cover_edges() -> None:
    empty: list[dict[str, Any]] = []
    assert _filter_scores_by_percentile(empty, 50) == []

    results = [
        {"score": 10, "id": "a"},
        {"score": 5, "id": "b"},
        {"score": 10, "id": "c"},
    ]

    filtered = _filter_scores_by_percentile(results, 50)
    assert {row["id"] for row in filtered} == {"a", "c"}

    top2 = _filter_scores_by_top_k(results, 2)
    assert {row["id"] for row in top2} == {"a", "c"}

    top_many = _filter_scores_by_top_k(results, 10)
    assert [row["id"] for row in top_many] == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_search_handles_http_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = DummyCtx()
    settings.content_strategy = "quick"

    class StatusClient:
        async def __aenter__(self) -> "StatusClient":
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def get(self, *_: object, **__: object) -> httpx.Response:
            request = httpx.Request("GET", "https://example.com/search")
            response = httpx.Response(500, request=request)
            raise httpx.HTTPStatusError(
                "boom", request=request, response=response
            )

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: StatusClient())

    with pytest.raises(SearchError):
        await search(ctx=ctx, query="q", time_range=None)

    assert any(level == "error" for level, _ in ctx.messages)

    class TransportClient:
        async def __aenter__(self) -> "TransportClient":
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def get(self, *_: object, **__: object) -> httpx.Response:
            raise httpx.TransportError("network down")

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_: TransportClient())

    with pytest.raises(SearchError):
        await search(ctx=ctx, query="q", time_range=None)

    assert any(level == "error" for level, _ in ctx.messages)


@pytest.mark.asyncio
async def test_search_handles_missing_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = DummyCtx()
    settings.content_strategy = "quick"

    stub_response = StubAsyncResponse(payload={})
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **_: StubAsyncClient(stub_response)
    )

    with pytest.raises(SearchError):
        await search(ctx=ctx, query="q", time_range=None)

    assert (
        "error",
        "Search error: 'results' not found in SearXNG response",
    ) in ctx.messages


@pytest.mark.asyncio
async def test_search_quick_strategy_uses_snippets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = DummyCtx()
    settings.content_strategy = "quick"
    settings.filter_score_percentile = None
    settings.filter_top_k = 10
    settings.content_limit = None

    payload = {
        "results": [
            {
                "title": "Result One",
                "content": "Snippet One",
                "url": "https://example.com/one",
                "score": 10,
            },
            {
                "title": "Result Two",
                "content": "Snippet Two",
                "url": "https://example.com/two",
                "score": 9,
            },
        ]
    }

    stub_response = StubAsyncResponse(payload=payload)
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **_: StubAsyncClient(stub_response)
    )

    results = await search(ctx=ctx, query="query", time_range=None)

    assert [r.content for r in results] == ["Snippet One", "Snippet Two"]


@pytest.mark.asyncio
async def test_search_unknown_strategy_warns_and_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = DummyCtx()
    # Intentional invalid strategy to exercise fallback handling
    settings.content_strategy = "invalid"  # type: ignore[assignment]
    settings.filter_score_percentile = None
    settings.filter_top_k = 10
    settings.content_limit = None

    payload = {
        "results": [
            {
                "title": "Result One",
                "content": "Snippet One",
                "url": "https://example.com/one",
                "score": 10,
            }
        ]
    }

    stub_response = StubAsyncResponse(payload=payload)
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **_: StubAsyncClient(stub_response)
    )

    results = await search(ctx=ctx, query="query", time_range=None)

    assert results[0].content == "Snippet One"
    assert any(level == "warning" for level, _ in ctx.messages)


@pytest.mark.asyncio
async def test_search_trimming_variants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = DummyCtx()
    settings.content_strategy = "quick"
    settings.filter_score_percentile = None
    settings.filter_top_k = 10

    base_payload = {
        "results": [
            {
                "title": "Result One",
                "content": "A" * 12,
                "url": "https://example.com/one",
                "score": 10,
            }
        ]
    }

    stub_response = StubAsyncResponse(payload=base_payload)
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **_: StubAsyncClient(stub_response)
    )

    settings.content_limit = None
    results = await search(ctx=ctx, query="query", time_range=None)
    assert results[0].content == "A" * 12

    settings.content_limit = 12
    results = await search(ctx=ctx, query="query", time_range=None)
    assert results[0].content == "A" * 12

    settings.content_limit = 5
    results = await search(ctx=ctx, query="query", time_range=None)
    assert results[0].content == "A" * 5


@pytest.mark.asyncio
async def test_fetch_url_handles_fetcher_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = DummyCtx()

    async def failing_fetch(*_: object, **__: object) -> StubFetcherResponse:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "powersearch_mcp.powersearch.StealthyFetcher.async_fetch",
        failing_fetch,
    )

    with pytest.raises(FetchError):
        await fetch_url(
            ctx=ctx, url="https://example.com/fail", fetch_timeout_ms=500
        )

    assert any("Fetcher failed" in message for _, message in ctx.messages)


@pytest.mark.asyncio
async def test_fetch_url_handles_missing_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = DummyCtx()

    async def ok_fetch(*_: object, **__: object) -> StubFetcherResponse:
        return StubFetcherResponse(html_content="<p>body</p>", status=200)

    monkeypatch.setattr(
        "powersearch_mcp.powersearch.StealthyFetcher.async_fetch",
        ok_fetch,
    )
    monkeypatch.setattr(
        "powersearch_mcp.powersearch.trafilatura.extract",
        lambda *_, **__: None,
    )

    with pytest.raises(FetchError):
        await fetch_url(
            ctx=ctx, url="https://example.com/none", fetch_timeout_ms=500
        )

    assert any("No content extracted" in message for _, message in ctx.messages)


@pytest.mark.asyncio
async def test_search_fetch_resilience_on_partial_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = DummyCtx()
    settings.content_strategy = "fetch"
    settings.filter_score_percentile = None
    settings.filter_top_k = 10
    settings.content_limit = None

    payload = {
        "results": [
            {
                "title": "Good",
                "content": "Snippet Good",
                "url": "https://example.com/good",
                "score": 10,
            },
            {
                "title": "Bad",
                "content": "Snippet Bad",
                "url": "https://example.com/bad",
                "score": 9,
            },
        ]
    }

    stub_response = StubAsyncResponse(payload=payload)
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **_: StubAsyncClient(stub_response)
    )

    async def conditional_fetch(url: str, **_: object) -> StubFetcherResponse:
        if "bad" in url:
            raise RuntimeError("fetch broke")
        return StubFetcherResponse(
            html_content="<p>good content</p>", status=200
        )

    monkeypatch.setattr(
        "powersearch_mcp.powersearch.StealthyFetcher.async_fetch",
        conditional_fetch,
    )
    monkeypatch.setattr(
        "powersearch_mcp.powersearch.trafilatura.extract",
        lambda *_, **__: "Cleaned good content",
    )

    results = await search(ctx=ctx, query="query", time_range=None)

    assert results[0].content == "Cleaned good content"
    assert results[1].content == "Snippet Bad"
    assert any(level == "error" for level, _ in ctx.messages)
