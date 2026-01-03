from pathlib import Path

import pytest
from pytest import MonkeyPatch

from powersearch_mcp.settings import ServerSettings


def test_server_settings_defaults_remain_stable(
    monkeypatch: MonkeyPatch,
) -> None:
    env_keys = {
        f"POWERSEARCH_{name.upper()}" for name in ServerSettings.model_fields
    }
    env_keys.update(
        {
            "FASTMCP_LOG_LEVEL",
            "POWERSEARCH_CACHE",
            "POWERSEARCH_CACHE_TTL_SECONDS",
            "FASTMCP_SERVER_AUTH",
        }
    )

    for key in env_keys:
        monkeypatch.delenv(key, raising=False)

    settings = ServerSettings(_env_file=None)

    assert settings.model_dump() == {
        "log_level": "INFO",
        "log_payloads": False,
        "log_estimate_tokens": False,
        "log_max_payload_length": 1000,
        "errorhandling_traceback": False,
        "errorhandling_transform": True,
        "retry_retries": 3,
        "retry_base_delay": 1.0,
        "retry_max_delay": 60.0,
        "retry_backoff_multiplier": 2.0,
        "cache_storage": None,
        "cache_ttl_sec": 3600,
        "authz_policy_path": None,
        "enable_audit_logging": True,
        "fallback_behavior": None,
        "openai_api_key": None,
        "openai_base_url": None,
        "openai_default_model": None,
    }


def test_server_settings_sampling_fallback_env(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("POWERSEARCH_FALLBACK_BEHAVIOR", "fallback")
    monkeypatch.setenv("POWERSEARCH_OPENAI_API_KEY", "SECRET")
    monkeypatch.setenv(
        "POWERSEARCH_OPENAI_BASE_URL",
        "https://litellm.example.internal/v1",
    )
    monkeypatch.setenv("POWERSEARCH_OPENAI_DEFAULT_MODEL", "gpt-oss-120b")

    settings = ServerSettings(_env_file=None)

    assert settings.fallback_behavior == "fallback"
    assert settings.openai_api_key == "SECRET"
    assert (
        str(settings.openai_base_url) == "https://litellm.example.internal/v1"
    )
    assert settings.openai_default_model == "gpt-oss-120b"


def test_authz_policy_requires_authentication(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("FASTMCP_SERVER_AUTH", raising=False)
    policy_path = tmp_path / "policy.json"
    policy_path.write_text("{}")

    with pytest.raises(ValueError, match="FASTMCP_SERVER_AUTH"):
        ServerSettings(authz_policy_path=str(policy_path), _env_file=None)


def test_authz_policy_allows_configured_auth(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(
        "FASTMCP_SERVER_AUTH",
        "fastmcp.server.auth.providers.jwt.JWTVerifier",
    )
    policy_path = tmp_path / "policy.json"
    policy_path.write_text("{}")

    settings = ServerSettings(
        authz_policy_path=str(policy_path), _env_file=None
    )

    assert settings.authz_policy_path == str(policy_path)
