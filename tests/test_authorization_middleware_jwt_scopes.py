from contextvars import ContextVar
from types import SimpleNamespace

import jwt
import pytest
from mcp.server.auth.middleware import auth_context

import powersearch_mcp.authorization_middleware as am
from powersearch_mcp.authorization_middleware import factory


def _make_token(*, scope: str, secret: str, sub: str = "user-1") -> str:
    return jwt.encode(
        {
            "sub": sub,
            "scope": scope,
        },
        secret,
        algorithm="HS256",
    )


@pytest.fixture(autouse=True)
def _jwt_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POWERSEARCH_AUTH_PUBLIC_KEY", "test-signing-secret")
    monkeypatch.setenv("POWERSEARCH_AUTH_ALGORITHM", "HS256")
    monkeypatch.setenv("POWERSEARCH_AUTHZ_JWT_SCOPES", "true")
    monkeypatch.delenv("POWERSEARCH_AUTH_JWKS_URI", raising=False)
    monkeypatch.delenv("POWERSEARCH_AUTH_ISSUER", raising=False)
    monkeypatch.delenv("POWERSEARCH_AUTH_AUDIENCE", raising=False)


@pytest.fixture
def _reset_auth_context() -> ContextVar[object | None]:
    token = auth_context.auth_context_var.set(None)
    try:
        yield auth_context.auth_context_var
    finally:
        auth_context.auth_context_var.reset(token)


def test_factory_requires_key_or_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POWERSEARCH_AUTH_PUBLIC_KEY", raising=False)
    middleware = None
    with pytest.raises(
        ValueError, match="Either public_key or jwks_uri must be provided"
    ):
        middleware = factory()
    if middleware is not None:  # pragma: no cover
        raise RuntimeError("Expected factory() to raise")


@pytest.mark.asyncio
async def test_verified_principal_includes_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    signing_secret = am.os.getenv("POWERSEARCH_AUTH_PUBLIC_KEY")
    if not signing_secret:
        raise RuntimeError("POWERSEARCH_AUTH_PUBLIC_KEY not set")
    token = _make_token(
        scope="powersearch:mcp:perm:read powersearch:mcp:perm:execute",
        secret=signing_secret,
    )

    middleware = factory()

    # Patch get_http_headers used by middleware module
    monkeypatch.setattr(
        am,
        "get_http_headers",
        lambda: {"authorization": f"Bearer {token}"},
    )

    principal = await middleware._verified_principal()  # noqa: SLF001
    if principal.attributes["claims"]["scope"] != [
        "powersearch:mcp:perm:read",
        "powersearch:mcp:perm:execute",
    ]:
        raise AssertionError("Unexpected scope mapping")


def test_extract_principal_stringifies_list_claims(
    _reset_auth_context: ContextVar[object | None],
) -> None:
    context_token = _reset_auth_context.set(
        SimpleNamespace(
            access_token=SimpleNamespace(
                claims={
                    "sub": "user-123",
                    "scope": ["alpha", "beta"],
                    "nested": {"roles": ["admin", "editor"]},
                }
            )
        )
    )

    try:
        principal = am.EunomiaJWTPrincipalMiddleware()._extract_principal()
    finally:
        _reset_auth_context.reset(context_token)

    if principal.uri != "client:user-123":
        raise AssertionError("Expected subject mapped to client URI")
    if principal.attributes["scope"] != "alpha beta":
        raise AssertionError("Scope should be stringified")
    if principal.attributes["nested"]["roles"] != "admin editor":
        raise AssertionError("Nested list should be stringified")


@pytest.mark.asyncio
async def test_invalid_token_falls_back_to_default_principal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    middleware = factory()

    monkeypatch.setattr(
        am,
        "get_http_headers",
        lambda: {"authorization": "Bearer not-a-real-jwt"},
    )

    principal = await middleware._verified_principal()  # noqa: SLF001

    # Default principal is the Eunomia middleware fallback.
    if not principal.uri.startswith("agent:"):
        raise AssertionError("Expected fallback principal")


def test_extract_principal_missing_auth_context(
    _reset_auth_context: ContextVar[object | None],
) -> None:
    token = _reset_auth_context.set(None)

    try:
        with pytest.raises(
            RuntimeError, match="Authentication context is missing"
        ):
            am.EunomiaJWTPrincipalMiddleware()._extract_principal()
    finally:
        _reset_auth_context.reset(token)


def test_extract_principal_missing_access_token(
    _reset_auth_context: ContextVar[object | None],
) -> None:
    token = _reset_auth_context.set(SimpleNamespace())

    try:
        with pytest.raises(
            RuntimeError,
            match="Authentication context is missing an access token",
        ):
            am.EunomiaJWTPrincipalMiddleware()._extract_principal()
    finally:
        _reset_auth_context.reset(token)


def test_extract_principal_missing_claims(
    _reset_auth_context: ContextVar[object | None],
) -> None:
    token = _reset_auth_context.set(
        SimpleNamespace(access_token=SimpleNamespace())
    )

    try:
        with pytest.raises(
            RuntimeError, match="does not expose a claims dictionary"
        ):
            am.EunomiaJWTPrincipalMiddleware()._extract_principal()
    finally:
        _reset_auth_context.reset(token)
