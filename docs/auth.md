# Authentication and Authorization for PowerSearch MCP

Secure the PowerSearch MCP Streamable HTTP transport with your identity provider while keeping the STDIO transport unauthenticated. This guide covers JSON Web Tokens (JWTs), opaque-token introspection, and the built-in Eunomia authorization policy.

## Audience and Scope

- Remote HTTP transport only; STDIO stays unauthenticated for trusted/local use.
- Headless MCP clients that bring their own access tokens from an external identity provider (IDP).

## Authentication Options

| Option | When to choose | Provider wiring | Notes |
| --- | --- | --- | --- |
| JWT (recommended) | IDP issues self-contained JWT access tokens (Keycloak, Auth0, WorkOS/AuthKit, most OIDC) | `RemoteAuthProvider` + `JWTVerifier` | No per-request network once JWKS cached; advertises trusted issuers and MCP base URL. |
| Opaque tokens | IDP only issues opaque bearer tokens | `IntrospectionTokenVerifier` | Calls the IDP RFC 7662 introspection endpoint on every request; expect higher latency. |

## Required Configuration (Environment First)

| Purpose | Variables | Details |
| --- | --- | --- |
| Select auth strategy | `FASTMCP_SERVER_AUTH` | `fastmcp.server.auth.RemoteAuthProvider` (JWT) or `fastmcp.server.auth.providers.introspection.IntrospectionTokenVerifier` (opaque). |
| JWT verification | `FASTMCP_SERVER_AUTH_JWT_JWKS_URI`, `FASTMCP_SERVER_AUTH_JWT_ISSUER`, `FASTMCP_SERVER_AUTH_JWT_AUDIENCE`, `FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES` | Scopes default to `powersearch:read`; set comma-separated scopes to enforce more (e.g., add `powersearch:execute`). |
| OAuth metadata for discovery (JWT path) | `FASTMCP_SERVER_AUTH_REMOTEAUTHPROVIDER_AUTHORIZATION_SERVERS`, `FASTMCP_SERVER_AUTH_REMOTEAUTHPROVIDER_BASE_URL` | Authorization servers list (issuer URLs) and public base URL of this MCP server; base URL must match what clients reach (no path). |
| Opaque token introspection | `FASTMCP_SERVER_AUTH_INTROSPECTION_INTROSPECTION_URL`, `FASTMCP_SERVER_AUTH_INTROSPECTION_CLIENT_ID`, `FASTMCP_SERVER_AUTH_INTROSPECTION_CLIENT_SECRET`, `FASTMCP_SERVER_AUTH_INTROSPECTION_REQUIRED_SCOPES` | Required only when using opaque tokens. One network call per request to the IDP. |
| Authorization policy | `POWERSEARCH_AUTHZ_POLICY_PATH` | Enables Eunomia middleware when the file exists; missing file fails startup. Example: `example-configs/mcp_policies.json`. |
| Session docket (HTTP transport) | `FASTMCP_DOCKET_URL`, `FASTMCP_DOCKET_CONCURRENCY` | Stores session state for Streamable HTTP. Defaults in `fastmcp-http-auth.json` use in-memory docket and concurrency 10. |

## Quickstart: JWT with Keycloak (Localhost)

1) Configure Keycloak to issue RS256 JWT access tokens: JWKS `http://127.0.0.1:8080/realms/example/protocol/openid-connect/certs`, issuer `http://127.0.0.1:8080/realms/example`, audience `powersearch-mcp`, scope `powersearch:read` (add `powersearch:execute` to enable tool calls).
2) Set environment (or `.env`) using [example-configs/example.env](example-configs/example.env); update JWKS/issuer/audience as needed.
3) Start HTTP transport: `fastmcp run fastmcp-http-auth.json --skip-env --project .`
4) Connect clients to `http://127.0.0.1:8099/mcp` with `Authorization: Bearer <token>`.

## Opaque Tokens via Introspection

1) Set `FASTMCP_SERVER_AUTH=fastmcp.server.auth.providers.introspection.IntrospectionTokenVerifier`.
2) Provide the introspection URL, client ID/secret, and required scopes.
3) Expect one IDP call per request; tune timeouts accordingly.

## Authorization with Eunomia (Default Deny)

- Enabled when `POWERSEARCH_AUTHZ_POLICY_PATH` points to an existing JSON policy; startup fails if the file is missing.
- Bundled example policy: [example-configs/mcp_policies.json](example-configs/mcp_policies.json).
- Default effect is `deny`; add allow rules for tools/prompts.
- Scope-driven allow-list pattern is recommended for stable onboarding.

### Scope Behavior (Bundled Policy)

With `FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES=powersearch:read`:

| Token scopes | Auth gate (JWT required scopes) | List tools/prompts | Execute tools (`search`, `fetch_url`) | Execute prompt (`internet_search_prompt`) |
| --- | --- | --- | --- | --- |
| `powersearch:read` | Passes | Allowed | Denied (policy requires execute) | Allowed |
| `powersearch:read, powersearch:execute` | Passes (both if configured) | Allowed | Allowed | Allowed |

- To permit tool execution, issue tokens including `powersearch:execute` and set `FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES=powersearch:read,powersearch:execute`.
- If any required scope is missing, the request is rejected before Eunomia evaluates policy.

## Operations and Expectations

- Base URL must match what clients use (example: `http://127.0.0.1:8099` with path `/mcp`).
- JWKS handles key rotation automatically; invalid issuer/audience/expiry returns 401. Missing scopes return 403 due to default-deny policy.
- Response caching is independent; authorization runs before tool execution.
- STDIO transport is intentionally unauthenticated—use only in trusted environments.
- Session docket defaults: `memory://` URL and concurrency 10 in `fastmcp-http-auth.json`; raise for heavier loads.

## References

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [OAuth 2.1](https://oauth.net/2.1/)
- [OpenID Connect](https://openid.net/specs/openid-connect-core-1_0.html) (OIDC)
- [JWT](https://datatracker.ietf.org/doc/html/rfc7519)
- [JWKS](https://datatracker.ietf.org/doc/html/rfc7517)
- [Token Introspection](https://datatracker.ietf.org/doc/html/rfc7662)
- [Eunomia authorization](https://gofastmcp.com/integrations/eunomia-authorization)
