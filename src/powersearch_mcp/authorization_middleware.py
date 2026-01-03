"""Eunomia-aware MCP auth middleware that normalizes JWT claims.

This module wires Eunomia policy evaluation into the MCP server and extracts
the current principal from the MCP auth context. It validates that an auth
context, access token, and claims are present, raising ``FastMCPError`` with
actionable guidance when something is missing. Because the Eunomia evaluation
engine currently expects scalar claim values, ``_stringify_claim_lists``
recursively converts list-valued claims into whitespace-separated strings
before constructing a ``PrincipalCheck`` for policy evaluation.
"""

from collections.abc import Mapping, Sequence

from eunomia.config import settings as eunomia_settings
from eunomia.server import EunomiaServer
from eunomia_core import schemas
from eunomia_mcp.bridge import EunomiaMode
from eunomia_mcp.middleware import EunomiaMcpMiddleware
from eunomia_mcp.utils import load_policy_config
from fastmcp.exceptions import FastMCPError
from mcp.server.auth.middleware.auth_context import auth_context_var

from powersearch_mcp.settings import server_settings

type ClaimValue = (
    str
    | int
    | float
    | bool
    | None
    | Mapping[str, "ClaimValue"]
    | Sequence["ClaimValue"]
)


def _stringify_claim_lists(value: ClaimValue) -> ClaimValue:
    if isinstance(value, Mapping):
        return {k: _stringify_claim_lists(v) for k, v in value.items()}
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        normalized_items = [_stringify_claim_lists(item) for item in value]
        return " ".join(str(item) for item in normalized_items)
    return value


class EunomiaJWTPrincipalMiddleware(EunomiaMcpMiddleware):  # type: ignore
    def _extract_principal(self) -> schemas.PrincipalCheck:
        auth_context = auth_context_var.get()
        if auth_context is None:
            raise FastMCPError(
                "Authentication context is missing; ensure RequireAuthMiddleware ran and a valid access token was provided."
            )

        access_token = getattr(auth_context, "access_token", None)
        if access_token is None:
            raise FastMCPError(
                "Authentication context is missing an access token; ensure your MCP auth provider is configured correctly."
            )

        claims = getattr(access_token, "claims", None)
        if not isinstance(claims, dict):
            raise FastMCPError(
                "Authentication token does not expose a claims dictionary; verify the token includes claim data."
            )

        # Insight: currently the Eunomia evaluation engine doesn't work
        # properly when claim contains list; see
        # eunomia.engine.evaluator.apply_operator(). As a workaround, we need
        # to convert claims that contain a list into strings separated by
        # whitespace.
        normalized_claims = _stringify_claim_lists(claims)
        if not isinstance(normalized_claims, Mapping):
            raise FastMCPError(
                "Normalized claims are not a mapping; ensure claim coercion preserved key/value pairs."
            )

        normalized_claims_dict = dict(normalized_claims)

        return schemas.PrincipalCheck(
            uri=f"client:{normalized_claims_dict.get('sub', 'unknown')}",
            attributes=normalized_claims_dict,
        )


def factory(policy_file: str) -> EunomiaJWTPrincipalMiddleware:
    eunomia_settings.ENGINE_SQL_DATABASE = False
    eunomia_settings.FETCHERS = {}

    server = EunomiaServer()
    policy = load_policy_config(policy_file)
    server.engine.add_policy(policy)

    return EunomiaJWTPrincipalMiddleware(
        mode=EunomiaMode.SERVER,
        eunomia_client=None,
        eunomia_server=server,
        enable_audit_logging=server_settings.enable_audit_logging,
    )


__all__ = [
    "ClaimValue",
    "EunomiaJWTPrincipalMiddleware",
    "EunomiaMode",
    "_stringify_claim_lists",
    "factory",
]
