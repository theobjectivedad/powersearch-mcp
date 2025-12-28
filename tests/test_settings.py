from __future__ import annotations

import logging
from pathlib import Path

import pytest
from key_value.aio.stores.disk import DiskStore
from key_value.aio.stores.memory import MemoryStore
from key_value.aio.stores.null import NullStore
from key_value.aio.stores.redis import RedisStore

from powersearch_mcp.settings import ServerSettings, build_key_value_store


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


def test_server_settings_error_handling_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("POWERSEARCH_ERRORHANDLING_TRACEBACK", raising=False)
    monkeypatch.delenv("POWERSEARCH_ERRORHANDLING_TRANSFORM", raising=False)
    monkeypatch.delenv("POWERSEARCH_RETRY_RETRIES", raising=False)
    monkeypatch.delenv("POWERSEARCH_RETRY_BASE_DELAY", raising=False)
    monkeypatch.delenv("POWERSEARCH_RETRY_MAX_DELAY", raising=False)
    monkeypatch.delenv("POWERSEARCH_RETRY_BACKOFF_MULTIPLIER", raising=False)

    local_settings = ServerSettings()

    assert local_settings.errorhandling_traceback is False
    assert local_settings.errorhandling_transform is True
    assert local_settings.retry_retries == 3
    assert local_settings.retry_base_delay == 1.0
    assert local_settings.retry_max_delay == 60.0
    assert local_settings.retry_backoff_multiplier == 2.0


def test_server_settings_error_handling_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("POWERSEARCH_ERRORHANDLING_TRACEBACK", "true")
    monkeypatch.setenv("POWERSEARCH_ERRORHANDLING_TRANSFORM", "false")
    monkeypatch.setenv("POWERSEARCH_RETRY_RETRIES", "5")
    monkeypatch.setenv("POWERSEARCH_RETRY_BASE_DELAY", "0.5")
    monkeypatch.setenv("POWERSEARCH_RETRY_MAX_DELAY", "10.5")
    monkeypatch.setenv("POWERSEARCH_RETRY_BACKOFF_MULTIPLIER", "1.25")

    local_settings = ServerSettings()

    assert local_settings.errorhandling_traceback is True
    assert local_settings.errorhandling_transform is False
    assert local_settings.retry_retries == 5
    assert local_settings.retry_base_delay == 0.5
    assert local_settings.retry_max_delay == 10.5
    assert local_settings.retry_backoff_multiplier == 1.25


def test_build_key_value_store_disabled() -> None:
    assert build_key_value_store(None) is None
    assert build_key_value_store("") is None
    assert build_key_value_store("none") is None


def test_build_key_value_store_memory_disk_and_null(tmp_path: Path) -> None:
    assert isinstance(build_key_value_store("memory"), MemoryStore)

    disk_dir = tmp_path
    disk_store = build_key_value_store(f"file://{disk_dir}")
    assert isinstance(disk_store, DiskStore)

    null_store = build_key_value_store("null")
    assert isinstance(null_store, NullStore)


def test_build_key_value_store_redis_and_invalid() -> None:
    redis_store = build_key_value_store("redis://localhost:6379/0")
    assert isinstance(redis_store, RedisStore)

    with pytest.raises(ValueError):
        build_key_value_store("unknown://backend")
