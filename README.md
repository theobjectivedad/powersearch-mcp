# PowerSearch MCP

![Lint, unit test status](https://img.shields.io/github/actions/workflow/status/theobjectivedad/powersearch-mcp/checks.yml?label=Lint%2FPyTest)
![Release status](https://img.shields.io/github/actions/workflow/status/theobjectivedad/powersearch-mcp/release.yml?label=Build)
![Publish status](https://img.shields.io/github/actions/workflow/status/theobjectivedad/powersearch-mcp/publish.yml?label=Publish)

![Project status](https://img.shields.io/pypi/status/powersearch-mcp?label=Status)
![License](https://img.shields.io/github/license/theobjectivedad/powersearch-mcp?label=License)
![Python Version](https://img.shields.io/pypi/pyversions/powersearch-mcp?label=Python)

![PyPi version](https://img.shields.io/pypi/v/powersearch-mcp?label=PyPi%20Version)
![PyPi downloads](https://img.shields.io/pypi/dm/powersearch-mcp?label=PyPi%20Downloads)

PowerSearch MCP helps AI agents search and retrieve content from the public web with fewer broken fetches, less boilerplate, and clean outputs ready to cite.

**Features:**

- ✅ [SearXNG](https://docs.searxng.org/)-backed meta search with configurable engines, language, safe-search, and pagination.
- ✅ Strong anti-bot fetching implementation via [Scrapling](https://github.com/D4Vinci/Scrapling) and [Camoufox](https://camoufox.com)
- ✅ Search response caching at the tool-level to memory, disk, and Redis storage backends
- ✅ Automatic retries with exponential backoff for both search and fetch operations
- ✅ AI Agent-friendly responses: HTML pages are converted to markdown automatically via [Trafilatura](https://github.com/adbar/trafilatura)
- ✅ Supports both STDIO and streaming HTTP transports
- ✅ Health check endpoint for HTTP transport
- ✅ Extensive [configuration](#configuration) suitable for many deployment scenarios

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

PowerSearch now relies entirely on the FastMCP CLI and the checked-in configuration files. Runtime behavior still comes from `POWERSEARCH_` environment variables (or a `.env` file).

- STDIO (default): `fastmcp run fastmcp.json --skip-env --project .` — best for Claude Desktop and Inspector.
- Streamable HTTP example: `fastmcp run fastmcp-http.json --skip-env --project .` — binds to `0.0.0.0:8092/mcp` with CORS enabled.
- Override deployment settings at launch with flags (for example `--transport stdio`, `--host 0.0.0.0`, `--port 8912`, `--path /custom`). CLI flags override the `deployment` block in the chosen config.

Both configs bake in the runtime dependencies to make first-time installs predictable; uv will reuse the local project via `--project .` and `editable` so local edits take effect. The HTTP app still exposes a `/health` endpoint and honors all `POWERSEARCH_` environment variables for search behavior.

To run the search backend in the background:

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

PowerSearch reads environment variables with the `POWERSEARCH_` prefix (also respected via a `.env` file). By design, configuration exists only as environment variables to make using the Power Search tool as simple as possible for AI agents.

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

### Middleware & Reliability

| Setting | What it does | When to change |
| --- | --- | --- |
| `POWERSEARCH_LOG_LEVEL` | Logging level for middleware; falls back to `FASTMCP_LOG_LEVEL` when unset. | Raise to `DEBUG`/`INFO` while troubleshooting; lower to `WARNING`/`ERROR` in production. |
| `POWERSEARCH_INCLUDE_PAYLOADS` | Include full MCP request/response bodies in logs. | Enable temporarily for debugging only; can expose user data. |
| `POWERSEARCH_INCLUDE_PAYLOAD_LENGTH` | Log payload length alongside metadata. | Pair with payload logging when sizes matter but full bodies are off. |
| `POWERSEARCH_ESTIMATE_PAYLOAD_TOKENS` | Log approximate token counts (length // 4). | Enable when monitoring token budgets. |
| `POWERSEARCH_MAX_PAYLOAD_LENGTH` | Cap logged payload characters. | Lower to reduce log volume; raise when debugging truncated bodies. |
| `POWERSEARCH_ERRORHANDLING_TRACEBACK` | Include tracebacks in error responses. | Enable only in non-production environments. |
| `POWERSEARCH_ERRORHANDLING_TRANSFORM` | Convert exceptions into MCP-friendly error responses. | Leave on unless you need raw exceptions for debugging. |
| `POWERSEARCH_RETRY_RETRIES` | Max retry attempts applied by retry middleware. | Increase for flaky upstreams; set to 0 to disable retries. |
| `POWERSEARCH_RETRY_BASE_DELAY` | Initial delay between retries (seconds). | Tune for backoff aggressiveness. |
| `POWERSEARCH_RETRY_MAX_DELAY` | Upper bound on backoff delay (seconds). | Prevent excessively long waits. |
| `POWERSEARCH_RETRY_BACKOFF_MULTIPLIER` | Exponential backoff multiplier. | Lower for gentler backoff; raise for faster escalation. |

### Caching

PowerSearch can cache tool responses (search and fetch_url) via FastMCP's response caching middleware. Caching is off by default.

| Setting | What it does | When to change |
| --- | --- | --- |
| `POWERSEARCH_CACHE` | Storage backend selector: `memory`, `null` (no-op, good for tests), `file:///path/to/dir`, or `redis://host:port/db`. Empty/`None` disables caching. | Enable for repeat queries or to avoid refetching the same URLs. Use `memory` for local dev, `file://` for lightweight persistence, and `redis://` for shared/distributed deployments. |
| `POWERSEARCH_CACHE_TTL_SEC` (alias: `POWERSEARCH_CACHE_TTL_SECONDS`) | TTL for cached tool responses (seconds). Defaults to 3600. | Shorten for fresher results; lengthen when upstream data changes rarely. |
