from collections.abc import Iterator
from contextvars import ContextVar
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol, cast

import pytest
from eunomia_core import schemas
from fastmcp.exceptions import FastMCPError
from mcp.server.auth.middleware import auth_context as auth_ctx

import powersearch_mcp.authorization_middleware as authorization_middleware
from powersearch_mcp.authorization_middleware import (
    EunomiaJWTPrincipalMiddleware,
    _stringify_claim_lists,
    factory,
)


class AuthenticatedUser(Protocol):
    access_token: Any | None


auth_context_var = cast(
    "ContextVar[AuthenticatedUser | None]", auth_ctx.auth_context_var
)


@pytest.fixture(autouse=True)
def clear_auth_context() -> Iterator[None]:
    token = auth_context_var.set(None)
    yield
    auth_context_var.reset(token)


def test_stringify_claim_lists_normalizes_nested_sequences() -> None:
    claims = {
        "sub": "user-123",
        "roles": ["reader", "writer"],
        "nested": {"scopes": ["one", "two"]},
        "list_of_dicts": [{"k": "v1"}, {"k": "v2"}],
    }

    normalized = _stringify_claim_lists(claims)

    assert normalized["roles"] == "reader writer"
    assert normalized["nested"]["scopes"] == "one two"
    assert normalized["list_of_dicts"] == "{'k': 'v1'} {'k': 'v2'}"


def test_extract_principal_normalizes_claims() -> None:
    middleware = object.__new__(EunomiaJWTPrincipalMiddleware)
    access_token = SimpleNamespace(
        claims={"sub": "abc", "roles": ["a", "b"], "aud": "aud1"}
    )
    auth_context_var.set(
        cast("AuthenticatedUser", SimpleNamespace(access_token=access_token))
    )

    principal = middleware._extract_principal()

    assert isinstance(principal, schemas.PrincipalCheck)
    assert principal.uri == "client:abc"
    assert principal.attributes["roles"] == "a b"
    assert principal.attributes["aud"] == "aud1"


def test_extract_principal_requires_auth_context() -> None:
    middleware = object.__new__(EunomiaJWTPrincipalMiddleware)

    with pytest.raises(FastMCPError, match="Authentication context is missing"):
        middleware._extract_principal()


def test_extract_principal_requires_access_token() -> None:
    middleware = object.__new__(EunomiaJWTPrincipalMiddleware)
    auth_context_var.set(cast("AuthenticatedUser", SimpleNamespace()))

    with pytest.raises(FastMCPError, match="missing an access token"):
        middleware._extract_principal()


def test_extract_principal_requires_claims_dict() -> None:
    middleware = object.__new__(EunomiaJWTPrincipalMiddleware)
    auth_context_var.set(
        cast(
            "AuthenticatedUser",
            SimpleNamespace(access_token=SimpleNamespace(claims=None)),
        )
    )

    with pytest.raises(FastMCPError, match="claims dictionary"):
        middleware._extract_principal()


def test_factory_loads_policy_and_wires_middleware(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    added_policies: list[object] = []
    seen_paths: list[str] = []

    class DummyEngine:
        def add_policy(self, policy: object) -> None:
            added_policies.append(policy)

    class DummyServer:
        def __init__(self) -> None:
            self.engine = DummyEngine()

    class DummyMiddleware:
        def __init__(
            self,
            *,
            mode: object,
            eunomia_client: object,
            eunomia_server: DummyServer,
            enable_audit_logging: bool,
        ) -> None:
            self.mode = mode
            self.eunomia_client = eunomia_client
            self.eunomia_server = eunomia_server
            self.enable_audit_logging = enable_audit_logging

    def fake_load_policy_config(path: str) -> object:
        seen_paths.append(path)
        return {"name": "policy-from-file"}

    monkeypatch.setattr(
        authorization_middleware,
        "EunomiaJWTPrincipalMiddleware",
        DummyMiddleware,
    )
    monkeypatch.setattr(authorization_middleware, "EunomiaServer", DummyServer)
    monkeypatch.setattr(
        authorization_middleware, "load_policy_config", fake_load_policy_config
    )

    policy_path = (
        Path(__file__).parent.parent
        / "example-configs"
        / "mcp_policies_jwt_scope.json"
    )

    middleware = factory(str(policy_path))

    assert seen_paths == [str(policy_path)]
    assert added_policies == [{"name": "policy-from-file"}]
    assert isinstance(middleware, DummyMiddleware)
    assert middleware.mode == authorization_middleware.EunomiaMode.SERVER
    assert middleware.eunomia_client is None
    assert isinstance(middleware.eunomia_server, DummyServer)
