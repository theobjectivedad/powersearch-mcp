# PowerSearch MCP

![Lint, unit test status](https://img.shields.io/github/actions/workflow/status/theobjectivedad/powersearch-mcp/checks.yml?label=Lint%2FPyTest)
![Release status](https://img.shields.io/github/actions/workflow/status/theobjectivedad/powersearch-mcp/release.yml?label=Build)
![Publish status](https://img.shields.io/github/actions/workflow/status/theobjectivedad/powersearch-mcp/publish.yml?label=Publish)

![Project status](https://img.shields.io/pypi/status/powersearch-mcp?label=Status)
![License](https://img.shields.io/github/license/theobjectivedad/powersearch-mcp?label=License)
![Python Version](https://img.shields.io/pypi/pyversions/powersearch-mcp?label=Python)

![PyPi version](https://img.shields.io/pypi/v/powersearch-mcp?label=PyPi%20Version)
![PyPi downloads](https://img.shields.io/pypi/dm/powersearch-mcp?label=PyPi%20Downloads)

PowerSearch MCP helps AI agents search and retrieve content from the public web with fewer broken fetches and clean, AI-friendly outputs ready to cite.

**Feature Roadmap:**

- ✅ [SearXNG](https://docs.searxng.org/)-backed meta search with configurable engines, language, safe-search, and pagination.
- ✅ Strong anti-bot fetching implementation via [Scrapling](https://github.com/D4Vinci/Scrapling) and [Camoufox](https://camoufox.com)
- ✅ Search response caching at the tool-level to memory, disk, and Redis storage backends
- ✅ Automatic retries with exponential backoff for both search and fetch operations
- ✅ AI Agent-friendly responses: HTML pages are converted to markdown automatically via [Trafilatura](https://github.com/adbar/trafilatura)
- ✅ Support for STDIO and streaming HTTP transports
- ✅ Health check endpoint for HTTP transport
- ✅ Extensive [configuration](#configuration) suitable for many deployment scenarios
- ✅ Authentication support for both JWT and opaque tokens
- ✅ Authorization support for embedded [Eunomia](https://github.com/whataboutyou-ai/eunomia) policies
- 🗓️ (Future) Auto summarization of search results via [MCP sampling](https://modelcontextprotocol.io/specification/2025-06-18/client/sampling)
- 🗓️ (Future) Client selectable synchronous (current behavior) or asynchronous [SEP-1686](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks) execution for search / fetch tools.
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
| `FASTMCP_SERVER_AUTH` | Auth provider selector (e.g., `fastmcp.server.auth.RemoteAuthProvider` for JWT, or `fastmcp.server.auth.providers.introspection.IntrospectionTokenVerifier` for opaque tokens). | When setting up authentication; choose based on your token type (JWT or opaque). |
| `FASTMCP_SERVER_AUTH_JWT_JWKS_URI` | JWKS endpoint for JWT signature validation. | When using JWT authentication; point to your identity provider's JWKS URI. |
| `FASTMCP_SERVER_AUTH_JWT_ISSUER` | Expected issuer for tokens. | When configuring JWT validation; set to match your identity provider's issuer. |
| `FASTMCP_SERVER_AUTH_JWT_AUDIENCE` | Expected audience for tokens. | When securing the server; specify the intended audience for tokens. |
| `FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES` | Required scopes on the token (default `powersearch:read`; add `powersearch:execute` to allow tool calls). | When enforcing authorization; list every scope a token must include to pass auth. |
| `FASTMCP_SERVER_AUTH_REMOTEAUTHPROVIDER_AUTHORIZATION_SERVERS` | Trusted authorization servers (discovery). | When using RemoteAuthProvider; list your authorization server URLs. |
| `FASTMCP_SERVER_AUTH_REMOTEAUTHPROVIDER_BASE_URL` | Public base URL of the MCP server (no path). | When deploying with RemoteAuthProvider; set the server's public URL. |
| `POWERSEARCH_AUTHZ_POLICY_PATH` | Path to the Eunomia JSON policy file. Server refuses to start if set and missing. | When enabling authorization policies; provide the path to your policy file. |
| `POWERSEARCH_ENABLE_AUDIT_LOGGING` | Enable Eunomia audit logging when authz middleware is active. | When you need audit logs for authorization decisions; set to true for compliance. |
| --- | --- | --- |
| `POWERSEARCH_CACHE` | Storage backend selector: `memory`, `null` (no-op, good for tests), `file:///path/to/dir`, or `redis://host:port/db`. Empty/`None` disables caching. | Enable for repeat queries or to avoid refetching the same URLs. Use `memory` for local dev, `file://` for lightweight persistence, and `redis://` for shared/distributed deployments. |
| `POWERSEARCH_CACHE_TTL_SEC` (alias: `POWERSEARCH_CACHE_TTL_SECONDS`) | TTL for cached tool responses (seconds). Defaults to 3600. | Shorten for fresher results; lengthen when upstream data changes rarely. |

### Authentication & Authorization

| Setting | What it does | When to change |
| --- | --- | --- |
| `FASTMCP_SERVER_AUTH` | Selects the FastMCP auth provider (e.g., RemoteAuthProvider for OAuth discovery plus token verification, JWTVerifier for self-contained JWTs, IntrospectionTokenVerifier for opaque tokens). | Switch based on how tokens are issued; use RemoteAuthProvider when you want clients to discover your IdP, pick JWT or introspection verifiers to match token type. |
| `FASTMCP_SERVER_AUTH_JWT_JWKS_URI` | JWKS endpoint used to verify JWT signatures. | Set whenever you validate JWTs; point at your identity provider's JWKS URL. |
| `FASTMCP_SERVER_AUTH_JWT_ISSUER` | Expected `iss` claim for JWTs. | Match this to your identity provider's issuer to block tokens from other issuers. |
| `FASTMCP_SERVER_AUTH_JWT_AUDIENCE` | Expected `aud` claim for JWTs. | Set to the audience your identity provider issues for this server; change when you re-register the app. |
| `FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES` | Scopes that must appear on accepted JWTs. | Use to enforce least privilege; add or adjust as you tighten or relax access. |
| `FASTMCP_SERVER_AUTH_REMOTEAUTHPROVIDER_AUTHORIZATION_SERVERS` | Authorization servers that RemoteAuthProvider should advertise for discovery. | Populate when RemoteAuthProvider is active so clients know which identity providers are trusted. |
| `FASTMCP_SERVER_AUTH_REMOTEAUTHPROVIDER_BASE_URL` | Public base URL of this MCP server for RemoteAuthProvider metadata. | Set to your public host (no path) when running over HTTP; update if the server URL changes. |
| `POWERSEARCH_AUTHZ_POLICY_PATH` | Path to the Eunomia JSON policy file; server refuses to start if set and missing. | Provide when enabling authorization and point at the policy you want enforced. |
| `POWERSEARCH_ENABLE_AUDIT_LOGGING` | Turns on Eunomia audit logging when authz middleware is enabled. | Enable for compliance or incident review; leave off to reduce log volume. |
