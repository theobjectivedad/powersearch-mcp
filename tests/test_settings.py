from pathlib import Path

import pytest
from pytest import MonkeyPatch

from powersearch_mcp.settings import ServerSettings


def test_authz_policy_requires_authentication(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("FASTMCP_SERVER_AUTH", raising=False)
    policy_path = tmp_path / "policy.json"
    policy_path.write_text("{}")

    with pytest.raises(ValueError, match="FASTMCP_SERVER_AUTH"):
        ServerSettings(authz_policy_path=str(policy_path))


def test_authz_policy_allows_configured_auth(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(
        "FASTMCP_SERVER_AUTH",
        "fastmcp.server.auth.providers.jwt.JWTVerifier",
    )
    policy_path = tmp_path / "policy.json"
    policy_path.write_text("{}")

    settings = ServerSettings(authz_policy_path=str(policy_path))

    assert settings.authz_policy_path == str(policy_path)
