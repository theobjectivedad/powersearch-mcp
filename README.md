# Power Search MCP

![Static analysis checks](https://github.com/theobjectivedad/powersearch-mcp/actions/workflows/checks.yml/badge.svg)
![Release status](https://github.com/theobjectivedad/powersearch-mcp/actions/workflows/release.yml/badge.svg)
![PyPi publish](https://github.com/theobjectivedad/powersearch-mcp/actions/workflows/publish.yml/badge.svg)

PowerSearch is an Internet search & content retrieval MCP server that can bypass common bot detection mechanisms, and returns markdown-formatted content optimized for AI agents. PowerSearch relies on a number of open source technologies, including:

- [SearXNG](https://docs.searxng.org/) Meta search engine capable of normalizing scores across many backend search engines and supports returning JSON formatted search results.
- [Scrapling](https://github.com/D4Vinci/Scrapling) Modern web scraping library.
- [Camoufox](https://camoufox.com/) Headless browser with strong anti-bot capabilities.
- [Trafilatura](https://github.com/adbar/trafilatura) For text extraction and HTML‑to‑Markdown conversion.

## Setup

If you haven't already, go ahead and run `make init` to set up the Python virtual environment and dependencies.

Next, initialize Camoufox:

```shell
camoufox fetch
```

Finally, run a local instance of SearXNG.

```shell
docker run --rm -it \
    --name searxng-local \
    -p 127.0.0.1:9876:8080 \
    --tmpfs /etc/searxng:rw,noexec,nosuid,size=16m \
    --tmpfs /tmp:rw,noexec,nosuid,size=512m \
    --cap-drop=ALL \
    --security-opt=no-new-privileges:true \
    --env=SEARXNG_SETTINGS_PATH=/settings.yml \
    --volume=$(pwd)/searxng.yaml:/settings.yml:ro \
    searxng/searxng
```

## Running the server

PowerSearch still reads runtime configuration from environment variables (or a `.env` file) with the `POWERSEARCH_` prefix. The CLI adds transport selection while keeping that behavior.

- Stdio (default): `powersearch-mcp`
- HTTP transport: `powersearch-mcp --transport http --host 0.0.0.0 --port 8912 --path /mcp`
- HTTPS: add `--ssl-certfile path/to/cert.pem --ssl-keyfile path/to/key.pem` (optionally `--ssl-ca-certs` for a custom bundle).

`--host`, `--port`, `--path`, and TLS flags also honor environment variables (`POWERSEARCH_HTTP_HOST`, `POWERSEARCH_HTTP_PORT`, `POWERSEARCH_HTTP_PATH`, `POWERSEARCH_HTTP_SSL_CERTFILE`, `POWERSEARCH_HTTP_SSL_KEYFILE`, `POWERSEARCH_HTTP_SSL_CA_CERTS`, `POWERSEARCH_HTTP_SSL_KEYFILE_PASSWORD`, `POWERSEARCH_HTTP_LOG_LEVEL`). The HTTP app exposes a `/health` endpoint returning a simple JSON payload.

Alternatively, you can always run the search engine in the background:

```shell
docker run -d \
    --name searxng-local \
    --pull=always \
    --restart unless-stopped \
    -p 127.0.0.1:9876:8080 \
    --tmpfs /etc/searxng:rw,noexec,nosuid,size=16m \
    --tmpfs /tmp:rw,noexec,nosuid,size=512m \
    --cap-drop=ALL \
    --security-opt=no-new-privileges:true \
    --health-cmd='python3 -c "import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:8080/\", timeout=3).read(1)"' \
    --health-interval=10s \
    --health-timeout=3s \
    --health-retries=10 \
    --health-start-period=15s \
    --env SEARXNG_SETTINGS_PATH=/settings.yml \
    --volume "$(pwd)/searxng.yaml:/settings.yml:ro" \
    searxng/searxng
```

## How Are Search Results Ranked?

SearXNG returns each hit with a score that already blends engine weight and position. PowerSearch keeps that score and applies two passes: a percentile cut and a top-K trim. By default it keeps results at or above the 75th percentile, then retains only the top 10. That combination aggressively drops weak hits while keeping a predictable result count.

If you set `POWERSEARCH_FILTER_SCORE_PERCENTILE` to `None`, the percentile cut is skipped and only the top-K pass runs. Increasing `POWERSEARCH_FILTER_TOP_K` widens the net but may slow things down if content fetching is enabled.

Content strategy matters too. With `fetch`, the tool will fetch each retained URL and run Trafilatura over it; higher K or looser filters mean more network work. With `quick`, PowerSearch leaves content as the SearXNG snippets, which is faster but less complete.

## Configuration

PowerSearch reads environment variables with the `POWERSEARCH_` prefix (also respected via a `.env` file). The table below shows when each setting matters.

By design, configuration exists only as environment variables to make using the Power Search tool as simple as possible for AI agents.

### Search Behavior

| Setting | What it does | When to change |
| --- | --- | --- |
| `POWERSEARCH_BASE_URL` | SearXNG search endpoint (should end with `/search`). | Point at your own SearXNG host or a different port. |
| `POWERSEARCH_ENGINES` | Comma-separated SearXNG engines. | Limit to a trusted subset (e.g., `duckduckgo,bing`). |
| `POWERSEARCH_LANGUAGE` | IETF language tag for queries. | Bias results toward a locale (e.g., `en`, `fr`). |
| `POWERSEARCH_SAFE_SEARCH` | Safe-search level (0, 1, 2). | Tweak content filtering; defaults to 1. |
| `POWERSEARCH_MAX_PAGE` | How many result pages to request. | Raise for broader coverage when latency is acceptable. |
| `POWERSEARCH_FILTER_SCORE_PERCENTILE` | Drops results below a score percentile. | Lower or disable (`None`) if you need long-tail hits. |
| `POWERSEARCH_FILTER_TOP_K` | Keep only the top K after scoring. | Increase for more results; decrease for faster downstream fetches. |
| `POWERSEARCH_CONTENT_STRATEGY` | `fetch` pulls pages; `quick` uses SearXNG snippets only. | Use `quick` when you cannot fetch pages or need speed. |
| `POWERSEARCH_CONTENT_LIMIT` | Character cap per result. | Raise to keep more text; set `None` to disable trimming. |
| `POWERSEARCH_TIMEOUT_SEC` | Total budget for search + fetch. | Increase on slow networks; decrease to fail fast. |
| `POWERSEARCH_HTTP2` | Enables HTTP/2 upstream. | Turn on if your network and SearXNG support it. |
| `POWERSEARCH_VERIFY` | TLS certificate verification. | Disable only for trusted dev setups with self-signed certs. |

### Content Extraction Behavior

| Setting | What it does | When to change |
| --- | --- | --- |
| `POWERSEARCH_TRAFILATURA_EXTRACTION_TIMEOUT` | Max seconds Trafilatura spends extracting (0 = no limit). | Add a cap if extractions hang on heavy pages. |
| `POWERSEARCH_TRAFILATURA_MIN_EXTRACTED_SIZE` | Minimum size of accepted text. | Raise to drop ultra-short pages; lower if small blurbs matter. |
| `POWERSEARCH_TRAFILATURA_MIN_DUPLCHECK_SIZE` | Minimum size for duplicate checking. | Bump up to reduce near-duplicate fragments. |
| `POWERSEARCH_TRAFILATURA_MAX_REPETITIONS` | Repetition cap for repeated blocks. | Lower to aggressively prune boilerplate. |
| `POWERSEARCH_TRAFILATURA_EXTENSIVE_DATE_SEARCH` | Enables extra date heuristics. | Turn off for speed if dates are irrelevant. |
| `POWERSEARCH_TRAFILATURA_INCLUDE_LINKS` | Keep hyperlinks in markdown output. | Enable if you want inline links retained. |
| `POWERSEARCH_TRAFILATURA_INCLUDE_IMAGES` | Keep image references. | Enable when image context is important. |
| `POWERSEARCH_TRAFILATURA_INCLUDE_TABLES` | Keep tables. | Disable only if tables bloat token counts. |
| `POWERSEARCH_TRAFILATURA_INCLUDE_COMMENTS` | Keep HTML comments. | Rarely needed; enable for debugging scraped pages. |
| `POWERSEARCH_TRAFILATURA_INCLUDE_FORMATTING` | Preserve formatting markup. | Enable if you need bold/italic cues; off for terser text. |
| `POWERSEARCH_TRAFILATURA_DEDUPLICATE` | Removes near-identical blocks. | Disable only if de-duplication cuts useful repeated info. |
| `POWERSEARCH_TRAFILATURA_FAVOR_PRECISION` | Prefers precision over recall. | Turn off to capture more content at the expense of noise. |

## Transports

PowerSearch MCP supports launching of both STDIO and HTTP transports.

### STDIO

Transport for Power MCP anc can be launched via `powersearch-mcp`.

### Streaming HTTP

Streamable HTTP is launched as an ASGI application via `uvicorn`.

Streamable HTTP transports will honor environment variables from a `.env` file in the startup directory. An example `.env` file can be found at: `example-configs/example.env`.

The streamable HTTP server supports a basic health check endpoint. The default URL path is `http://localhost:8092/health`

By default, the URL path is the standard `/mcp`.

The streamable HTTP transport can be launched via an internal `uvicorn` ASGI server (easiest, most common) or via your own ASGI server by referencing `app.py`.
