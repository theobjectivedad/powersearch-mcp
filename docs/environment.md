# Environment Configuration

PowerSearch reads environment variables with the `POWERSEARCH_` prefix (also respected via a `.env` file). By design, configuration exists only as environment variables to make using the Power Search tool as simple as possible for AI agents.

## Search Behavior

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
| `POWERSEARCH_SUMMARY_CONTENT_LIMIT` | Character cap per result when summarizing. | Set to keep summary context lean; leave unset for no extra trimming. |
| `POWERSEARCH_SUMMARY_CHUNK_SIZE` | Results per chunk when map-reduce is enabled. | Lower for tighter prompts; raise to reduce the number of sampling calls. |
| `POWERSEARCH_SUMMARY_TEMPERATURE` | Temperature used for summary sampling. | Keep near 0 for deterministic summaries; raise slightly for variety. |
| `POWERSEARCH_SUMMARY_MAX_TOKENS` | Max tokens requested from the client LLM for summaries. | Adjust to fit your client model limits; set `None` to leave unset. |
| `POWERSEARCH_TIMEOUT_SEC` | Total budget for search + fetch. | Increase on slow networks; decrease to fail fast. |
| `POWERSEARCH_HTTP2` | Enables HTTP/2 upstream. | Turn on if your network and SearXNG support it. |
| `POWERSEARCH_VERIFY` | TLS certificate verification. | Disable only for trusted dev setups with self-signed certs. |

## Content Extraction Behavior

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

## Middleware & Reliability

| Setting | What it does | When to change |
| --- | --- | --- |
| `POWERSEARCH_LOG_LEVEL` | Logging level for middleware; falls back to `FASTMCP_LOG_LEVEL` when unset. | Raise to `DEBUG`/`INFO` while troubleshooting; lower to `WARNING`/`ERROR` in production. |
| `POWERSEARCH_LOG_PAYLOADS` | Include full MCP request/response bodies in logs. | Enable temporarily for debugging only; can expose user data. |
| `POWERSEARCH_LOG_ESTIMATE_TOKENS` | Log approximate token counts (length // 4). | Enable when monitoring token budgets. |
| `POWERSEARCH_LOG_MAX_PAYLOAD_LENGTH` | Cap logged payload characters. | Lower to reduce log volume; raise when debugging truncated bodies. |

Payload lengths are always included in middleware logs to aid debugging.
| `POWERSEARCH_ERRORHANDLING_TRACEBACK` | Include tracebacks in error responses. | Enable only in non-production environments. |
| `POWERSEARCH_ERRORHANDLING_TRANSFORM` | Convert exceptions into MCP-friendly error responses. | Leave on unless you need raw exceptions for debugging. |
| `POWERSEARCH_RETRY_RETRIES` | Max retry attempts applied by retry middleware. | Increase for flaky upstreams; set to 0 to disable retries. |
| `POWERSEARCH_RETRY_BASE_DELAY` | Initial delay between retries (seconds). | Tune for backoff aggressiveness. |
| `POWERSEARCH_RETRY_MAX_DELAY` | Upper bound on backoff delay (seconds). | Prevent excessively long waits. |
| `POWERSEARCH_RETRY_BACKOFF_MULTIPLIER` | Exponential backoff multiplier. | Lower for gentler backoff; raise for faster escalation. |
| `FASTMCP_DOCKET_URL` | Session docket store for Streamable HTTP (e.g., `memory://`, `redis://host:port/db`). | Switch to Redis or another backend when you need persistent/distributed HTTP sessions. |
| `FASTMCP_DOCKET_CONCURRENCY` | Max concurrent docket operations. | Increase for higher HTTP session throughput; lower to limit resource use. |

## Sampling Fallback

| Setting | What it does | When to change |
| --- | --- | --- |
| `POWERSEARCH_FALLBACK_BEHAVIOR` | FastMCP sampling handler behavior (e.g., `fallback`) advertised when a server-side handler is configured. | Set to `fallback` when you want the server to call the OpenAI-compatible handler if the client lacks sampling support. |
| `POWERSEARCH_OPENAI_API_KEY` | API key used by the OpenAI-compatible sampling handler. | Provide when enabling server-side sampling fallback. |
| `POWERSEARCH_OPENAI_BASE_URL` | Optional base URL for OpenAI-compatible providers (e.g., LiteLLM proxy). | Set when using a proxy or non-default OpenAI endpoint. |
| `POWERSEARCH_OPENAI_DEFAULT_MODEL` | Default model requested by the OpenAI sampling handler. | Choose the deployed model name that matches your provider. |

## Caching

PowerSearch can cache tool responses (search and fetch_url) via FastMCP's response caching middleware. Caching is off by default.

| Setting | What it does | When to change |
| --- | --- | --- |
| `POWERSEARCH_CACHE` | Storage backend selector: `memory`, `null` (no-op, good for tests), `file:///path/to/dir`, or `redis://host:port/db`. Empty/`None` disables caching. | Enable for repeat queries or to avoid refetching the same URLs. Use `memory` for local dev, `file://` for lightweight persistence, and `redis://` for shared/distributed deployments. |
| `POWERSEARCH_CACHE_TTL_SEC` (alias: `POWERSEARCH_CACHE_TTL_SECONDS`) | TTL for cached tool responses (seconds). Defaults to 3600. | Shorten for fresher results; lengthen when upstream data changes rarely. |

## Authentication & Authorization

See [docs/auth.md](docs/auth.md) for full details.

| Setting | What it does | When to change |
| --- | --- | --- |
| `FASTMCP_SERVER_AUTH` | Selects the FastMCP auth provider (e.g., `fastmcp.server.auth.providers.auth0.Auth0Provider` for interactive OAuth, `fastmcp.server.auth.providers.jwt.JWTVerifier` for headless JWT validation). | Choose the provider that matches how your tokens are obtained (interactive vs headless). |
| `FASTMCP_SERVER_AUTH_AUTH0_CONFIG_URL` | OIDC discovery URL for Auth0/Keycloak (scenario 1). | Set when using the interactive OAuth flow so clients can discover the IdP. |
| `FASTMCP_SERVER_AUTH_AUTH0_CLIENT_ID` | OAuth client ID registered for PowerSearch MCP. | Provide when using Auth0/Keycloak OAuth. |
| `FASTMCP_SERVER_AUTH_AUTH0_AUDIENCE` | API audience that tokens must target. | Set to the audience configured in your IdP for PowerSearch MCP. |
| `FASTMCP_SERVER_AUTH_AUTH0_CLIENT_SECRET` | OAuth client secret for the MCP server registration. | Required for Auth0/Keycloak OAuth server-side flow. |
| `FASTMCP_SERVER_AUTH_AUTH0_BASE_URL` | Public base URL of the MCP server (no path) for OAuth redirects. | Set when using the interactive OAuth flow. |
| `FASTMCP_SERVER_AUTH_JWT_JWKS_URI` | JWKS endpoint used to verify JWT signatures (scenario 2). | Set for headless JWT validation when tokens are pre-issued. |
| `FASTMCP_SERVER_AUTH_JWT_ISSUER` | Expected `iss` claim for JWTs. | Match to your identity provider's issuer to block tokens from other issuers. |
| `FASTMCP_SERVER_AUTH_JWT_AUDIENCE` | Expected `aud` claim for JWTs. | Set to the audience your IdP issues for this server. |
| `FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES` | Scopes that must appear on accepted JWTs. | Use to enforce least privilege for headless JWT flows. |
| `POWERSEARCH_AUTHZ_POLICY_PATH` | Path to the Eunomia JSON policy file; server refuses to start if set and missing. | Provide when enabling authorization and point at the policy you want enforced. |
| `POWERSEARCH_ENABLE_AUDIT_LOGGING` | Turns on Eunomia audit logging when authz middleware is enabled. | Enable for compliance or incident review; leave off to reduce log volume. |
