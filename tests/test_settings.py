from __future__ import annotations

import logging

import pytest

from powersearch_mcp.settings import ServerSettings


def test_server_settings_default_log_level_uses_fastmcp_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FASTMCP_LOG_LEVEL", "DEBUG")
    monkeypatch.delenv("POWERSEARCH_LOG_LEVEL", raising=False)

    local_settings = ServerSettings()

    assert local_settings.log_level_value() == logging.DEBUG


def test_server_settings_payload_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POWERSEARCH_INCLUDE_PAYLOADS", "true")
    monkeypatch.setenv("POWERSEARCH_INCLUDE_PAYLOAD_LENGTH", "true")
    monkeypatch.setenv("POWERSEARCH_ESTIMATE_PAYLOAD_TOKENS", "true")
    monkeypatch.setenv("POWERSEARCH_MAX_PAYLOAD_LENGTH", "123")

    local_settings = ServerSettings()

    assert local_settings.include_payloads is True
    assert local_settings.include_payload_length is True
    assert local_settings.estimate_payload_tokens is True
    assert local_settings.max_payload_length == 123
