from dataclasses import dataclass
from types import TracebackType
from typing import Any

import httpx
import pytest

from powersearch_mcp import powersearch
from powersearch_mcp.powersearch import (
    FetchError,
    MessageSink,
    SearchError,
    _fetch_url,
    _filter_scores_by_percentile,
    _filter_scores_by_top_k,
    search,
    settings,
)


class RecordingSink(MessageSink):
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    async def info(self, message: str) -> None:  # noqa: D401 - simple recorder
        self.infos.append(message)

    async def warning(self, message: str) -> None:  # noqa: D401 - simple recorder
        self.warnings.append(message)

    async def error(self, message: str) -> None:  # noqa: D401 - simple recorder
        self.errors.append(message)


@dataclass
class StubResponse:
    payload: dict[str, Any]
    status_code: int = 200

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=httpx.Request("GET", "http://stub"),
                response=httpx.Response(status_code=self.status_code),
            )

    def json(self) -> dict[str, Any]:
        return self.payload


class StubAsyncClient:
    def __init__(self, response: StubResponse) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def __aenter__(self) -> "StubAsyncClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:  # pragma: no cover - no cleanup
        return None

    async def get(self, url: str, params: dict[str, Any]) -> StubResponse:
        self.calls.append((url, params))
        return self.response


@pytest.mark.parametrize(
    ("scores", "percentile", "expected_titles"),
    [
        ([10, 5, 1], 50, [10, 5]),
        ([1, 1, 1], None, [1, 1, 1]),
        ([], 75, []),
    ],
)
def test_filter_scores_by_percentile(
    scores: list[int], percentile: float | None, expected_titles: list[int]
) -> None:
    results = [
        {"title": f"t{i}", "score": score, "url": f"u{i}", "content": f"c{i}"}
        for i, score in enumerate(scores)
    ]

    filtered = _filter_scores_by_percentile(results, percentile)

    assert [item["score"] for item in filtered] == expected_titles


def test_filter_scores_by_top_k_orders_by_score() -> None:
    results = [
        {"title": "a", "score": 1, "url": "u1", "content": "c1"},
        {"title": "b", "score": 5, "url": "u2", "content": "c2"},
        {"title": "c", "score": 3, "url": "u3", "content": "c3"},
    ]

    filtered = _filter_scores_by_top_k(results, k=2)

    assert [item["title"] for item in filtered] == ["b", "c"]


@pytest.mark.asyncio
async def test_search_invalid_time_range_raises_and_logs() -> None:
    sink = RecordingSink()

    with pytest.raises(SearchError):
        await search(sink, query="x", time_range="century")

    assert sink.errors


@pytest.mark.asyncio
async def test_search_returns_quick_results_without_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = RecordingSink()
    stub_response = StubResponse(
        payload={
            "results": [
                {
                    "title": "t1",
                    "url": "http://one",
                    "content": "c1",
                    "score": 1,
                },
                {
                    "title": "t2",
                    "url": "http://two",
                    "content": "c2",
                    "score": 2,
                },
            ]
        }
    )

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **_: StubAsyncClient(stub_response)
    )
    monkeypatch.setattr(settings, "content_strategy", "quick")
    monkeypatch.setattr(settings, "filter_score_percentile", None)
    monkeypatch.setattr(settings, "filter_top_k", 2)

    results = await search(sink, query="hello", time_range=None)

    assert len(results) == 2
    assert results[0].content == "c1"
    assert not sink.errors


@pytest.mark.asyncio
async def test_search_filters_out_all_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = RecordingSink()
    stub_response = StubResponse(payload={"results": []})
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **_: StubAsyncClient(stub_response)
    )

    results = await search(sink, query="none", time_range=None)

    assert results == []
    assert any("zero results" in msg for msg in sink.warnings)


@pytest.mark.asyncio
async def test_search_missing_results_key_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = RecordingSink()
    stub_response = StubResponse(payload={"unexpected": []})
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **_: StubAsyncClient(stub_response)
    )

    with pytest.raises(SearchError):
        await search(sink, query="oops")

    assert sink.errors


@pytest.mark.asyncio
async def test_search_fetch_strategy_uses_fetch_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = RecordingSink()
    stub_response = StubResponse(
        payload={
            "results": [
                {
                    "title": "t1",
                    "url": "http://one",
                    "content": "snippet1",
                    "score": 1,
                },
                {
                    "title": "t2",
                    "url": "http://two",
                    "content": "snippet2",
                    "score": 2,
                },
            ]
        }
    )

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **_: StubAsyncClient(stub_response)
    )
    monkeypatch.setattr(settings, "content_strategy", "fetch")
    monkeypatch.setattr(settings, "filter_score_percentile", None)
    monkeypatch.setattr(settings, "filter_top_k", 2)

    async def fake_fetch(
        ctx: MessageSink, url: str, fetch_timeout_ms: int
    ) -> str:
        if url.endswith("two"):
            raise FetchError("boom")
        return f"md for {url}"

    monkeypatch.setattr(powersearch, "_fetch_url", fake_fetch)

    results = await search(sink, query="hello")

    assert results[0].content == "md for http://one"
    assert results[1].content == "snippet2"
    assert sink.errors


@dataclass
class FetcherResponse:
    status: int
    html_content: str


@pytest.mark.asyncio
async def test_fetch_url_cleans_and_limits_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = RecordingSink()

    async def fake_fetcher(**_: Any) -> FetcherResponse:
        return FetcherResponse(status=200, html_content="<p>Hi</p>\n\n\nWorld")

    monkeypatch.setattr(
        powersearch.StealthyFetcher, "async_fetch", fake_fetcher
    )
    monkeypatch.setattr(
        powersearch,
        "trafilatura",
        type("T", (), {"extract": lambda *_, **__: "Hello\n\n\nWorld"}),
    )
    monkeypatch.setattr(settings, "content_limit", 50)

    content = await _fetch_url(
        sink, url="http://example.com", fetch_timeout_ms=1000
    )

    assert content == "Hello\n\nWorld"


@pytest.mark.asyncio
async def test_fetch_url_raises_on_bad_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = RecordingSink()

    async def fake_fetcher(**_: Any) -> FetcherResponse:
        return FetcherResponse(status=500, html_content="body")

    monkeypatch.setattr(
        powersearch.StealthyFetcher, "async_fetch", fake_fetcher
    )

    with pytest.raises(FetchError):
        await _fetch_url(sink, url="http://bad", fetch_timeout_ms=100)

    assert sink.errors


@pytest.mark.asyncio
async def test_fetch_url_handles_empty_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sink = RecordingSink()

    async def fake_fetcher(**_: Any) -> FetcherResponse:
        return FetcherResponse(status=200, html_content="<p>Nothing</p>")

    monkeypatch.setattr(
        powersearch.StealthyFetcher, "async_fetch", fake_fetcher
    )
    monkeypatch.setattr(
        powersearch,
        "trafilatura",
        type("T", (), {"extract": lambda *_, **__: None}),
    )

    content = await _fetch_url(sink, url="http://empty", fetch_timeout_ms=100)

    assert content == ""
    assert any("No content" in msg for msg in sink.errors)
