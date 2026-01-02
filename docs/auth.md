# Authentication and Authorization for PowerSearch MCP

PowerSearch MCP can run open or protected. Authentication and authorization are driven by FastMCP configuration, so you can plug in different identity providers without changing PowerSearch code. This guide shows how to enable auth, how the embedded Eunomia policy engine is used, and two common deployment patterns.

## How authentication is configured

- FastMCP providers: Set `FASTMCP_SERVER_AUTH` to the full class path of any FastMCP auth provider (Auth0, WorkOS AuthKit, Descope, Supabase, Scalekit, OAuth introspection, plain JWT verification, and others). Provider-specific environment variables supply issuer metadata, client IDs, secrets, scopes, and JWKS URIs.
- Transport: Authentication is relevant for HTTP transports. STDIO mode typically runs without auth.
- User interaction vs headless: Providers such as `Auth0Provider` initiate an OAuth 2.1/OIDC authorization code flow that requires a human to sign in and consent. Headless modes such as `JWTVerifier` validate already-issued tokens and are suited for server-to-server calls.

## How authorization works here

PowerSearch MCP bundles a lightweight, embedded Eunomia policy evaluator. Policies are loaded from a JSON file on disk pointed to by `POWERSEARCH_AUTHZ_POLICY_PATH`. The policy model assumes the authorization server issues JWTs that already contain the claims you want to enforce (roles or scopes). There is no external, centralized policy service in this setup; the MCP server evaluates the static policy file against the JWT claims it receives. Enable audit logging with `POWERSEARCH_ENABLE_AUDIT_LOGGING=true` to capture allow/deny decisions.

## Scenario 1: Interactive OAuth (role-based)

Use this when human users run an MCP client that can open a browser, sign in with your identity provider, and return with an access token containing a role claim. The provider advertises its discovery metadata, so clients know how to authenticate.

Example `.env` for Auth0:

```env
FASTMCP_SERVER_AUTH=fastmcp.server.auth.providers.auth0.Auth0Provider
FASTMCP_SERVER_AUTH_AUTH0_CONFIG_URL=https://{YOUR_AS_SERVER_DOMAIN}/.well-known/openid-configuration
FASTMCP_SERVER_AUTH_AUTH0_CLIENT_ID=powersearch-mcp-proxy
FASTMCP_SERVER_AUTH_AUTH0_AUDIENCE=powersearch:mcp
FASTMCP_SERVER_AUTH_AUTH0_CLIENT_SECRET={YOUR_SECRET}
FASTMCP_SERVER_AUTH_AUTH0_BASE_URL=http://127.0.0.1:8099
POWERSEARCH_AUTHZ_POLICY_PATH=example-configs/mcp_policies_oidc_role.json
POWERSEARCH_ENABLE_AUDIT_LOGGING=true
```

When to use:

- You want the MCP client to follow a standard OAuth 2.1/OIDC authorization code flow with PKCE.
- Human users must log in and consent in a browser.
- The authorization server issues a role claim (for example `role=admin|editor|viewer`), and the Eunomia policy file maps those roles to allowed tools/resources.

## Scenario 2: Headless JWT (scope-based)

Use this when an MCP client (or an upstream app hosting the client) already has a JWT and simply forwards it to PowerSearch MCP. This bypasses MCP discovery/PKCE and is common for service-to-service calls, scheduled jobs, or hosted apps that manage their own sessions.

Example `.env` for direct JWT verification:

```env
FASTMCP_SERVER_AUTH=fastmcp.server.auth.providers.jwt.JWTVerifier
FASTMCP_SERVER_AUTH_JWT_JWKS_URI=https://{YOUR_AS_SERVER_DOMAIN}/protocol/openid-connect/certs
FASTMCP_SERVER_AUTH_JWT_ISSUER=https://{YOUR_AS_SERVER_DOMAIN}
FASTMCP_SERVER_AUTH_JWT_AUDIENCE=powersearch:mcp
FASTMCP_SERVER_AUTH_JWT_REQUIRED_SCOPES=powersearch:mcp:perm:read
POWERSEARCH_AUTHZ_POLICY_PATH=example-configs/mcp_policies_jwt_scope.json
POWERSEARCH_ENABLE_AUDIT_LOGGING=true
```

When to use:

- Tokens are minted elsewhere and delivered to the MCP client out-of-band (for example, a hosted UI that already holds a bearer token).
- You want a headless, non-interactive flow—no browser prompts, no MCP discovery metadata needed.
- Authorization is driven by scopes in the JWT (for example `powersearch:mcp:perm:read`), and the Eunomia policy file enforces which scopes are required for each tool/resource.

## Tips

- Keep policy files versioned alongside your deployment to avoid drift between auth claims and allowed actions.
- Rotate client secrets and signing keys at the identity provider; FastMCP will pick up changes via discovery or JWKS caching rules.
- If you add a new provider, set `FASTMCP_SERVER_AUTH` accordingly and point `POWERSEARCH_AUTHZ_POLICY_PATH` at a policy file that matches the claims that provider issues.

## References

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [OAuth 2.1](https://oauth.net/2.1/)
- [OpenID Connect](https://openid.net/specs/openid-connect-core-1_0.html) (OIDC)
- [JWT](https://datatracker.ietf.org/doc/html/rfc7519)
- [JWKS](https://datatracker.ietf.org/doc/html/rfc7517)
- [Token Introspection](https://datatracker.ietf.org/doc/html/rfc7662)
- [Eunomia authorization](https://gofastmcp.com/integrations/eunomia-authorization)
