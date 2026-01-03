# Environment Configuration

PowerSearch reads environment variables with the POWERSEARCH_ prefix (or from a `.env` file). The tables below use two columns: the setting name and a combined description that explains what it does and when you might change it.

## General PowerSearch Server Settings

| Setting | Details |
| --- | --- |
| `POWERSEARCH_LOG_LEVEL` | Middleware log level; falls back to `FASTMCP_LOG_LEVEL` when unset. Raise to DEBUG/INFO for troubleshooting, lower to WARNING/ERROR in production. |
| `POWERSEARCH_LOG_PAYLOADS` | When true, logs MCP request/response bodies. Enable only temporarily for debugging because payloads may contain sensitive data. |
| `POWERSEARCH_LOG_ESTIMATE_TOKENS` | Adds approximate token counts (length // 4) to payload logs; useful for monitoring budgets. |
| `POWERSEARCH_LOG_MAX_PAYLOAD_LENGTH` | Caps logged payload characters; lower to reduce log volume, raise if payloads are truncated while debugging. |
| `POWERSEARCH_ERRORHANDLING_TRACEBACK` | Includes Python tracebacks in error responses; keep off in production, on in dev to speed debugging. |
| `POWERSEARCH_ERRORHANDLING_TRANSFORM` | Converts exceptions into MCP-friendly errors; turn off only if you need raw exceptions during deep debugging. |

## SearXNG, fetch, and ranking settings

| Setting | Details |
| --- | --- |
| `POWERSEARCH_BASE_URL` | SearXNG search endpoint (should end with /search); point at your SearXNG host or a different port. |
| `POWERSEARCH_ENGINES` | Comma-separated list of SearXNG engines; limit to trusted sources (e.g., duckduckgo,bing). |
| `POWERSEARCH_LANGUAGE` | IETF language tag for queries (e.g., en, fr) to bias results to a locale. |
| `POWERSEARCH_SAFE_SEARCH` | Safe-search level 0/1/2; raise for stricter filtering, lower for more permissive results. |
| `POWERSEARCH_MAX_PAGE` | Number of result pages to request; raise for broader coverage when latency is acceptable. |
| `POWERSEARCH_FILTER_SCORE_PERCENTILE` | Drops results below this score percentile; lower or set None for long-tail hits. |
| `POWERSEARCH_FILTER_TOP_K` | Keeps only the top K after scoring; raise for more recall, lower for speed. |
| `POWERSEARCH_CONTENT_STRATEGY` | fetch pulls full pages; quick keeps SearXNG snippets only—use quick when you cannot fetch pages or need speed. |
| `POWERSEARCH_CONTENT_LIMIT` | Character cap per result; raise to keep more text, set None to disable trimming. |
| `POWERSEARCH_TIMEOUT_SEC` | Total timeout budget (search + fetch) in seconds; raise on slow networks, lower to fail fast. |
| `POWERSEARCH_HTTP2` | Enables HTTP/2 upstream when supported; useful for performance on capable networks. |
| `POWERSEARCH_VERIFY` | TLS verification flag; disable only for trusted dev setups with self-signed certs. |

### How Are Search Results Ranked?

SearXNG returns each hit with a score that already blends engine weight and position. PowerSearch keeps that score and applies two passes: a percentile cut and a top-K trim. By default it keeps results at or above the 75th percentile, then retains only the top 10. That combination aggressively drops weak hits while keeping a predictable result count.

If you set `POWERSEARCH_FILTER_SCORE_PERCENTILE` to `None`, the percentile cut is skipped and only the top-K pass runs. Increasing `POWERSEARCH_FILTER_TOP_K` widens the net but may slow things down if content fetching is enabled.

Content strategy matters too. With `fetch`, the tool will fetch each retained URL and run Trafilatura over it; higher K or looser filters mean more network work. With `quick`, PowerSearch leaves content as the SearXNG snippets, which is faster but less complete.

## Content Extraction Settings

| Setting | Details |
| --- | --- |
| `POWERSEARCH_TRAFILATURA_EXTRACTION_TIMEOUT` | Max seconds trafilatura spends extracting (0 disables the limit); cap if extractions hang on heavy pages. |
| `POWERSEARCH_TRAFILATURA_MIN_EXTRACTED_SIZE` | Minimum accepted text size; raise to drop ultra-short pages, lower if small blurbs matter. |
| `POWERSEARCH_TRAFILATURA_MIN_DUPLCHECK_SIZE` | Minimum size for duplicate checking; increase to reduce near-duplicate fragments. |
| `POWERSEARCH_TRAFILATURA_MAX_REPETITIONS` | Cap on repeated content blocks; lower to aggressively prune boilerplate. |
| `POWERSEARCH_TRAFILATURA_EXTENSIVE_DATE_SEARCH` | Enables extra date heuristics; turn off for speed if dates are irrelevant. |
| `POWERSEARCH_TRAFILATURA_INCLUDE_LINKS` | Keeps hyperlinks in extracted markdown; enable when inline links are needed. |
| `POWERSEARCH_TRAFILATURA_INCLUDE_IMAGES` | Keeps image references; enable when image context is important. |
| `POWERSEARCH_TRAFILATURA_INCLUDE_TABLES` | Keeps tables; disable only if they bloat token counts. |
| `POWERSEARCH_TRAFILATURA_INCLUDE_COMMENTS` | Keeps HTML comments; rarely needed outside debugging. |
| `POWERSEARCH_TRAFILATURA_INCLUDE_FORMATTING` | Preserves formatting markup; enable if bold/italic cues matter, off for terser text. |
| `POWERSEARCH_TRAFILATURA_DEDUPLICATE` | Removes near-identical blocks; disable only if de-duplication drops useful repeats. |
| `POWERSEARCH_TRAFILATURA_FAVOR_PRECISION` | Prefers precision over recall; turn off to capture more content at the expense of noise. |

## Summary Search Settings

| Setting | Details |
| --- | --- |
| `POWERSEARCH_SUMMARY_CONTENT_LIMIT` | Per-result character cap applied only during summary searches; keep unset for no extra trimming. |
| `POWERSEARCH_SUMMARY_CHUNK_SIZE` | Results per chunk when map-reduce summarization runs; lower for tighter prompts, raise to reduce sampling calls. |
| `POWERSEARCH_SUMMARY_TEMPERATURE` | Sampling temperature for summaries; keep near 0 for determinism, bump slightly for variety. |
| `POWERSEARCH_SUMMARY_MAX_TOKENS` | Max tokens requested from the client LLM for summaries; adjust to fit model limits or set None to leave unset. |

## Sampling fallback settings

| Setting | Details |
| --- | --- |
| `POWERSEARCH_FALLBACK_BEHAVIOR` | FastMCP sampling handler behavior (fallback or always); advertise fallback when clients may lack sampling support. |
| `POWERSEARCH_OPENAI_API_KEY` | API key for the OpenAI-compatible sampling handler; required when fallback is enabled. |
| `POWERSEARCH_OPENAI_BASE_URL` | Optional base URL for OpenAI-compatible providers (e.g., LiteLLM proxy); set when using a proxy or non-default endpoint. |
| `POWERSEARCH_OPENAI_DEFAULT_MODEL` | Default model name for the OpenAI sampling handler; set to the deployed model you expect to use. |

## Response Cache Settings

| Setting | Details |
| --- | --- |
| `POWERSEARCH_CACHE` | Response cache backend selector: memory, null (no-op, good for tests), `file:///path`, or `redis://host:port/db`. Empty/None disables caching. |
| `POWERSEARCH_CACHE_TTL_SEC` | TTL for cached tool responses in seconds (alias: `POWERSEARCH_CACHE_TTL_SECONDS`); shorten for fresher results, lengthen when upstream data changes rarely. |

## Retry Settings

| Setting | Details |
| --- | --- |
| `POWERSEARCH_RETRY_RETRIES` | Max retry attempts from retry middleware; raise for flaky upstreams, set 0 to disable. |
| `POWERSEARCH_RETRY_BASE_DELAY` | Initial delay between retries (seconds); tune for backoff aggressiveness. |
| `POWERSEARCH_RETRY_MAX_DELAY` | Upper bound on backoff delay (seconds); prevents excessively long waits. |
| `POWERSEARCH_RETRY_BACKOFF_MULTIPLIER` | Exponential backoff multiplier; lower for gentler backoff, raise for faster escalation. |

## FastMCP settings

| Setting | Details |
| --- | --- |
| `FASTMCP_LOG_LEVEL` | Global FastMCP log level; raise to DEBUG/INFO for troubleshooting, lower for production. |
| `FASTMCP_SHOW_CLI_BANNER` | Toggles CLI banner output; set false for quieter logs in automation. |
| `FASTMCP_MASK_ERROR_DETAILS` | Hides detailed error info from clients; keep true in production for safety. |
| `FASTMCP_STRICT_INPUT_VALIDATION` | Enforces strict tool input validation; keep true to block coercion, false for more permissive behavior. |
| `FASTMCP_INCLUDE_FASTMCP_META` | Includes FastMCP metadata in responses; disable to reduce payload size. |
| `FASTMCP_STATELESS_HTTP` | Enables stateless HTTP mode; keep true for simple deployments. |
| `FASTMCP_DOCKET_URL` | Session docket store for Streamable HTTP (e.g., `memory://` or `redis://host:port/db`); switch to Redis for persistence/distribution. |
| `FASTMCP_DOCKET_CONCURRENCY` | Max concurrent docket operations; raise for higher HTTP session throughput, lower to limit resource use. |

## Authentication / Authorization

When `POWERSEARCH_AUTHZ_POLICY_PATH` is set, `FASTMCP_SERVER_AUTH` must also be configured or the server refuses to start. See [auth.md](auth.md) for deeper guidance.

### Example 1, MCP client uses human-in-the-loop OAuth flow to get JWT

| Setting | Details |
| --- | --- |
| `FASTMCP_SERVER_AUTH` | fastmcp.server.auth.providers.auth0.Auth0Provider enables interactive OAuth. |
| `FASTMCP_SERVER_AUTH_AUTH0_CONFIG_URL` | OIDC discovery URL (e.g., https://YOUR_DOMAIN/.well-known/openid-configuration). |
| `FASTMCP_SERVER_AUTH_AUTH0_CLIENT_ID` | OAuth client ID registered for PowerSearch MCP. |
| `FASTMCP_SERVER_AUTH_AUTH0_AUDIENCE` | API audience that issued tokens must target. |
| `FASTMCP_SERVER_AUTH_AUTH0_CLIENT_SECRET` | OAuth client secret for the MCP server registration. |
| `FASTMCP_SERVER_AUTH_AUTH0_BASE_URL` | Public base URL of the MCP server (no path) for OAuth redirects. |
| `POWERSEARCH_AUTHZ_POLICY_PATH` | Eunomia policy file path (e.g., `example-configs/mcp_policies_oidc_role.json`); required for authorization enforcement. |
| `POWERSEARCH_ENABLE_AUDIT_LOGGING` | Enables Eunomia audit logging while authorization is active. |

### Example 2, MCP client gets its own JWT and sends to MCP server

| Setting | Details |
| --- | --- |
| `FASTMCP_SERVER_AUTH` | fastmcp.server.auth.providers.jwt.JWTVerifier enables headless JWT verification. |
| `FASTMCP_SERVER_AUTH_JWT_JWKS_URI` | JWKS endpoint used to verify JWT signatures (e.g., https://YOUR_DOMAIN/openid-connect/certs). |
| `FASTMCP_SERVER_AUTH_JWT_ISSUER` | Expected iss claim; blocks tokens from other issuers. |
| `FASTMCP_SERVER_AUTH_JWT_AUDIENCE` | Expected aud claim for JWTs (e.g., `powersearch:mcp`). |
| `FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES` | Required scopes (e.g., `powersearch:mcp:perm:read`) enforcing least privilege. |
| `POWERSEARCH_AUTHZ_POLICY_PATH` | Eunomia policy file path (e.g., `example-configs/mcp_policies_jwt_scope.json`); required for authorization enforcement. |
| `POWERSEARCH_ENABLE_AUDIT_LOGGING` | Enables Eunomia audit logging while authorization is active. |
