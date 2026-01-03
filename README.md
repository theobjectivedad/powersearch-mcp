# PowerSearch MCP

![Lint, unit test status](https://img.shields.io/github/actions/workflow/status/theobjectivedad/powersearch-mcp/checks.yml?label=Lint%2FPyTest)
![Release status](https://img.shields.io/github/actions/workflow/status/theobjectivedad/powersearch-mcp/release.yml?label=Build)
![Publish status](https://img.shields.io/github/actions/workflow/status/theobjectivedad/powersearch-mcp/publish.yml?label=Publish)

![Project status](https://img.shields.io/pypi/status/powersearch-mcp?label=Status)
![License](https://img.shields.io/github/license/theobjectivedad/powersearch-mcp?label=License)
![Python Version](https://img.shields.io/pypi/pyversions/powersearch-mcp?label=Python)
![PyPi version](https://img.shields.io/pypi/v/powersearch-mcp?label=PyPi%20Version)V

PowerSearch MCP helps AI agents search and retrieve content from the public web with fewer broken fetches and clean, AI-friendly outputs ready to cite.

**Feature Roadmap:**

- ✅ [SearXNG](https://docs.searxng.org/)-backed meta search with configurable engines, language, safe-search, and pagination
- ✅ Strong anti-bot fetching implementation via [Scrapling](https://github.com/D4Vinci/Scrapling) and [Camoufox](https://camoufox.com)
- ✅ Search response caching at the tool-level to memory, disk, and Redis storage backends
- ✅ Automatic retries with exponential backoff for both search and fetch operations
- ✅ AI Agent-friendly responses: HTML pages are converted to markdown automatically via [Trafilatura](https://github.com/adbar/trafilatura)
- ✅ Support for STDIO and streaming HTTP transports
- ✅ Health check endpoint for HTTP transport
- ✅ Extensive [configuration](#configuration) suitable for many deployment scenarios
- ✅ Authentication support for both JWT and opaque tokens
- ✅ Authorization support for embedded [Eunomia](https://github.com/whataboutyou-ai/eunomia) policies
- ✅ Auto summarization of search results via [MCP sampling](https://modelcontextprotocol.io/specification/2025-06-18/client/sampling)
- 🗓️ (Future) Client selectable synchronous (current behavior) or asynchronous [SEP-1686](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks) execution for search / fetch tools
- 🗓️ (Future) Containerization, publish public image
- 🗓️ (Future) Prometheus metrics exporter
- 🗓️ (Future) Helm chart

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
