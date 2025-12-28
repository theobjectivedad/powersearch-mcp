# Authentication & Authorization for PowerSearch MCP

This guide explains how to secure PowerSearch MCP for headless MCP clients using an external identity provider (IDP). It covers both JWT validation (preferred) and opaque-token introspection, plus the embedded Eunomia policy file.

## What is supported

- Remote OAuth with external IDP: use FastMCP `RemoteAuthProvider` + `JWTVerifier` for self-contained JWT access tokens.
- Opaque tokens: switch the verifier to `IntrospectionTokenVerifier` and point it at the IDP's RFC 7662 endpoint.
- Authorization: Eunomia middleware with a bundled JSON policy file; no separate Eunomia service/DB. Default stance is deny unless policy allows.
- Transports: Authentication applies to Streamable HTTP only. STDIO remains unauthenticated by design.

## Choosing JWT vs opaque tokens

- Prefer JWTs (self-contained):
  - No per-request network calls once JWKS keys are cached.
  - Works out of the box with Keycloak, Auth0, WorkOS/AuthKit, and most OIDC-compliant IDPs.
- Use opaque tokens only if your IDP will not issue JWTs:
  - Requires the introspection endpoint for every request.
  - Slightly higher latency; keep timeouts reasonable.

## Key configuration (environment-first)

- Core selector: `FASTMCP_SERVER_AUTH`
  - JWT path (recommended): `fastmcp.server.auth.RemoteAuthProvider`
  - Opaque path: `fastmcp.server.auth.providers.introspection.IntrospectionTokenVerifier`
- JWT verifier inputs:
  - `FASTMCP_SERVER_AUTH_JWT_JWKS_URI`
  - `FASTMCP_SERVER_AUTH_JWT_ISSUER`
  - `FASTMCP_SERVER_AUTH_JWT_AUDIENCE`
  - `FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES` (comma/space/JSON list; defaults to `powersearch:read`)
- RemoteAuth metadata for discovery:
  - `FASTMCP_SERVER_AUTH_REMOTEAUTHPROVIDER_AUTHORIZATION_SERVERS` (list or single URL of trusted issuers)
  - `FASTMCP_SERVER_AUTH_REMOTEAUTHPROVIDER_BASE_URL` (public base URL of the MCP server; defaults to localhost in the example env)
- Opaque/introspection inputs (if you choose opaque tokens):
  - `FASTMCP_SERVER_AUTH_INTROSPECTION_INTROSPECTION_URL`
  - `FASTMCP_SERVER_AUTH_INTROSPECTION_CLIENT_ID`
  - `FASTMCP_SERVER_AUTH_INTROSPECTION_CLIENT_SECRET`
  - `FASTMCP_SERVER_AUTH_INTROSPECTION_REQUIRED_SCOPES`
- Authorization policy (static file):
  - `POWERSEARCH_AUTHZ_POLICY_PATH` → path to a Eunomia JSON policy file. When set and present, authorization middleware is enabled.
- HTTP session docket (Streamable HTTP transport):
  - `FASTMCP_DOCKET_URL` (e.g., `memory://`, `redis://host:port/db`) stores session state.
  - `FASTMCP_DOCKET_CONCURRENCY` caps concurrent session handling; raise it for heavier loads.

## Quickstart (Keycloak + JWT, localhost)

1. Configure Keycloak realm/client to issue JWT access tokens (RS256):

- JWKS URI (default): `http://127.0.0.1:8080/realms/example/protocol/openid-connect/certs`
- Issuer: `http://127.0.0.1:8080/realms/example`
- Audience: the client ID you assign to PowerSearch (e.g., `powersearch-mcp`).
- Scopes: add a scope like `powersearch:read` and include it in issued tokens.

1. Set env (or `.env`) using the sample in [example-configs/example.env](example-configs/example.env):

- `FASTMCP_SERVER_AUTH=fastmcp.server.auth.RemoteAuthProvider`
- `FASTMCP_SERVER_AUTH_JWT_JWKS_URI=...` (Keycloak JWKS)
- `FASTMCP_SERVER_AUTH_JWT_ISSUER=...` (realm issuer)
- `FASTMCP_SERVER_AUTH_JWT_AUDIENCE=powersearch-mcp`
- `FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES=powersearch:read`
  - Add `,powersearch:execute` if you want tokens to be able to call tools.
- `FASTMCP_SERVER_AUTH_REMOTEAUTHPROVIDER_AUTHORIZATION_SERVERS=...` (realm issuer URL)
- `FASTMCP_SERVER_AUTH_REMOTEAUTHPROVIDER_BASE_URL=http://127.0.0.1:8099`
- `POWERSEARCH_AUTHZ_POLICY_PATH=example-configs/mcp_policies.json`

1. Run HTTP transport: `fastmcp run fastmcp-http-auth.json --skip-env --project .`

- Clients connect to `http://127.0.0.1:8099/mcp` with `Authorization: Bearer <token>`.
- STDIO transport remains unauthenticated; use only in trusted contexts.

## Opaque tokens (if your IDP requires them)

Set `FASTMCP_SERVER_AUTH=fastmcp.server.auth.providers.introspection.IntrospectionTokenVerifier` and provide the introspection URL, client credentials, and required scopes. Expect a network call to the IDP on each request.

## Authorization with Eunomia (static file)

- The middleware loads when `POWERSEARCH_AUTHZ_POLICY_PATH` points to an existing JSON policy. The bundled example is [example-configs/mcp_policies.json](example-configs/mcp_policies.json).
- Default effect should be `deny`; add allow rules for tools/prompts you want exposed.
- Recommended pattern: scope → allow-list mapping. Keep scopes stable so onboarding new clients is IDP-only.
- Anti-pattern: per-tenant bespoke rules that require frequent policy changes and redeploys. Prefer stable scopes and shared policy where possible.

### Scope behavior with the bundled policy

With `FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES` set to the default `powersearch:read`:

| Token scopes present | Auth gate (JWT required scopes) | Listing tools/prompts | Execute tools (`search`, `fetch_url`) | Execute prompt (`internet_search_prompt`) |
| --- | --- | --- | --- | --- |
| `powersearch:read` | ✅ passes | ✅ allowed | ❌ denied (policy requires execute) | ✅ allowed |
| `powersearch:read, powersearch:execute` | ✅ passes (needs both if configured) | ✅ allowed | ✅ allowed | ✅ allowed |

- To permit tool execution, issue tokens that include `powersearch:execute` **and** set `FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES=powersearch:read,powersearch:execute` so the auth gate enforces both.
- If a token is missing any scope listed in `FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES`, the request is rejected before Eunomia policies run.

## Operations and expectations

- Base URL: `FASTMCP_SERVER_AUTH_REMOTEAUTHPROVIDER_BASE_URL` must match the public MCP base (no path). The example uses `http://127.0.0.1:8099` for local testing.
- Key rotation: JWKS-based JWT verification handles rotation automatically.
- Failure behavior: expired/invalid issuer/audience → 401; missing scope → 403 via Eunomia (default deny).
- Caching: Response caching is independent; authorization runs before tool execution.
- STDIO: not authenticated; avoid exposing STDIO in untrusted environments.
