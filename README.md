# PowerSearch MCP

![Lint, unit test status](https://img.shields.io/github/actions/workflow/status/theobjectivedad/powersearch-mcp/checks.yml?label=Lint%2FPyTest)
![Release status](https://img.shields.io/github/actions/workflow/status/theobjectivedad/powersearch-mcp/release.yml?label=Build)
![Publish status](https://img.shields.io/github/actions/workflow/status/theobjectivedad/powersearch-mcp/publish.yml?label=Publish)

![Project status](https://img.shields.io/pypi/status/powersearch-mcp?label=Status)
![License](https://img.shields.io/github/license/theobjectivedad/powersearch-mcp?label=License)
![Python Version](https://img.shields.io/pypi/pyversions/powersearch-mcp?label=Python)
![PyPi version](https://img.shields.io/pypi/v/powersearch-mcp?label=PyPi%20Version)

PowerSearch MCP helps AI agents search and retrieve content from the public web with fewer broken fetches and clean, AI-friendly outputs ready to cite.

## TL;DR

**Step 1**: Clone the repository then run initialize the virtual environment:

```shell
git clone https://github.com/theobjectivedad/powersearch-mcp.git
```

**Step 2**: Initialize the virtual environment:

```shell
cd powersearch-mcp
make init
```

**Step 3**: Activate the virtual environment:

```shell
source .venv/bin/activate
```

**Step 4**: Create a `.env` file with your desired configuration, use `example-configs/example.env` as a starting point.

```shell
cp example-configs/example.env .env
```

**Step 5**: (Optional) run a local instance of SearXNG:

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

**Step 6**: Run PowerSearch via FastMCP:

```shell
fastmcp run \
    src/powersearch_mcp/app.py \
    --transport=streamable-http \
    --skip-source \
    --skip-env
```

**Step 7**: Point your AI agent at <http://localhost:8099/mcp> to start searching the web!

## Feature Roadmap

- ✅ [SearXNG](https://docs.searxng.org/)-backed meta search with configurable engines, language, safe-search, and pagination
- ✅ Strong anti-bot fetching implementation via [Scrapling](https://github.com/D4Vinci/Scrapling) and [Camoufox](https://camoufox.com)
- ✅ Search response caching at the tool-level to memory, disk, and Redis storage backends
- ✅ Automatic retries with exponential backoff for both search and fetch operations
- ✅ AI Agent-friendly responses: HTML pages are converted to markdown automatically via [Trafilatura](https://github.com/adbar/trafilatura)
- ✅ Support for STDIO and streaming HTTP transports
- ✅ Health check endpoint for HTTP transport
- ✅ Extensive [configuration](https://github.com/theobjectivedad/powersearch-mcp/blob/master/docs/configuration.md) suitable for many deployment scenarios
- ✅ [Authentication support](https://github.com/theobjectivedad/powersearch-mcp/blob/master/docs/auth.md) for both JWT and opaque tokens
- ✅ [Authorization support](https://github.com/theobjectivedad/powersearch-mcp/blob/master/docs/auth.md#how-authorization-works-here) for embedded [Eunomia](https://github.com/whataboutyou-ai/eunomia) policies
- ✅ Auto summarization of search results via [MCP sampling](https://modelcontextprotocol.io/specification/2025-06-18/client/sampling)
- ✅ Optional server-side fallback for clients that don't support MCP sampling
- ✅ Public Docker image on [Docker Hub](https://hub.docker.com/r/theobjectivedad/powersearch-mcp)
- 🗓️ (Future) Client selectable synchronous (current behavior) or asynchronous [SEP-1686](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks) execution for search / fetch tools
- 🗓️ (Future) Prometheus metrics exporter
- 🗓️ (Future) Helm chart
