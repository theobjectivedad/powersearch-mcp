"""Configuration models for PowerSearch MCP server and core search logic."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Literal, no_type_check

from key_value.aio.stores.disk import DiskStore
from key_value.aio.stores.memory import MemoryStore
from key_value.aio.stores.null import NullStore
from key_value.aio.stores.redis import RedisStore
from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    HttpUrl,
    TypeAdapter,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from key_value.aio.protocols.key_value import AsyncKeyValue

_env_file_setting = os.getenv("POWERSEARCH_ENV_FILE", ".env")

DEFAULT_BASE_URL: HttpUrl = TypeAdapter(HttpUrl).validate_python(
    "http://127.0.0.1:8099"
)


class PowerSearchSettings(BaseSettings):
    """Runtime configuration for Power Search sourced from environment."""

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        env_file=_env_file_setting,
        env_nested_delimiter="__",
        env_prefix="POWERSEARCH_",
        extra="ignore",
        nested_model_default_partial_update=True,
        validate_assignment=True,
    )

    base_url: HttpUrl = Field(
        default=DEFAULT_BASE_URL,
        description="Base SearXNG search URL (should end with /search).",
    )
    engines: list[str] = Field(
        default_factory=list,
        description="Comma-separated SearXNG engines to query.",
    )
    language: str = Field(
        default="en",
        description="IETF language tag passed to SearXNG.",
    )
    safe_search: int = Field(
        default=1,
        ge=0,
        le=2,
        description="Safe search level expected by SearXNG (0, 1, or 2).",
    )
    max_page: int = Field(
        default=1,
        ge=1,
        description="Number of result pages to request from SearXNG.",
    )
    filter_score_percentile: float | None = Field(
        default=75.0,
        ge=0,
        le=100,
        description=(
            "Score percentile cutoff; set to None to disable percentile filtering."
        ),
    )
    filter_top_k: int = Field(
        default=10,
        ge=1,
        description="Maximum results retained after filtering by score.",
    )
    content_strategy: Literal["quick", "fetch"] = Field(
        default="fetch",
        description=(
            "How to populate result content: quick (use SearXNG snippet) or fetch full pages."
        ),
    )
    content_limit: int | None = Field(
        default=None,
        ge=0,
        description="Trim each result's content to this many characters; None to disable.",
    )
    summary_content_limit: int | None = Field(
        default=None,
        ge=0,
        description=(
            "Optional per-result character cap applied only to summary searches; "
            "None leaves summary content untrimmed."
        ),
    )
    summary_chunk_size: int = Field(
        default=4,
        ge=1,
        description=(
            "How many results to include per chunk when running map-reduce summarization."
        ),
    )
    summary_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Temperature used for sampling-based summaries (0 is most deterministic).",
    )
    summary_max_tokens: int | None = Field(
        default=800,
        ge=1,
        description=(
            "Maximum tokens requested from the client LLM during summary sampling; None leaves it unset."
        ),
    )
    timeout_sec: int = Field(
        default=20,
        gt=0,
        description="Total timeout budget (seconds) for search plus content handling.",
    )
    http2: bool = Field(
        default=False,
        description="Enable HTTP/2 for upstream requests when supported.",
    )
    verify: bool = Field(
        default=True,
        description="Verify TLS certificates for upstream requests.",
    )
    trafilatura_extraction_timeout: float = Field(
        default=0.0,
        ge=0,
        description="Seconds trafilatura may spend extracting; 0 disables the limit.",
    )
    trafilatura_min_extracted_size: int = Field(
        default=100,
        ge=0,
        description="Minimum extracted text size required to accept content.",
    )
    trafilatura_min_duplcheck_size: int = Field(
        default=100,
        ge=0,
        description="Minimum size used by trafilatura's duplicate check.",
    )
    trafilatura_max_repetitions: int = Field(
        default=2,
        ge=0,
        description="Maximum repeated content blocks retained before trimming.",
    )
    trafilatura_extensive_date_search: bool = Field(
        default=True,
        description="Enable trafilatura's extensive date search heuristics.",
    )
    trafilatura_include_links: bool = Field(
        default=False,
        description="Whether to include links in extracted markdown.",
    )
    trafilatura_include_images: bool = Field(
        default=False,
        description="Whether to include images in extracted markdown.",
    )
    trafilatura_include_tables: bool = Field(
        default=True,
        description="Whether to include tables in extracted markdown.",
    )
    trafilatura_include_comments: bool = Field(
        default=False,
        description="Whether to include HTML comments in extracted markdown.",
    )
    trafilatura_include_formatting: bool = Field(
        default=False,
        description="Whether to preserve formatting markup from the source.",
    )
    trafilatura_deduplicate: bool = Field(
        default=True,
        description="Deduplicate near-identical blocks while extracting.",
    )
    trafilatura_favor_precision: bool = Field(
        default=True,
        description="Favor precision over recall when extracting content.",
    )

    @field_validator("engines", mode="before")
    @classmethod
    def parse_engines(
        cls, value: str | list[str] | None
    ) -> str | list[str] | None:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @field_validator("engines")
    @classmethod
    def ensure_engines(cls, value: list[str]) -> list[str]:
        return [engine for engine in value if engine]


class ServerSettings(BaseSettings):
    """Settings that govern MCP server behavior and middleware."""

    model_config = SettingsConfigDict(
        env_prefix="POWERSEARCH_",
        env_file=_env_file_setting,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str | int | None = Field(
        default=None,
        description=(
            "Logging level for middleware; defaults to FASTMCP_LOG_LEVEL or INFO."
        ),
    )
    log_payloads: bool = Field(
        default=False,
        validation_alias=AliasChoices("log_payloads", "include_payloads"),
        description="Include MCP request/response payload bodies in logs.",
    )
    log_estimate_tokens: bool = Field(
        default=False,
        validation_alias=AliasChoices(
            "log_estimate_tokens", "estimate_payload_tokens"
        ),
        description="Estimate token counts (length // 4) when logging payloads.",
    )
    log_max_payload_length: int = Field(
        default=1000,
        ge=0,
        validation_alias=AliasChoices(
            "log_max_payload_length", "max_payload_length"
        ),
        description="Maximum payload characters to log when payload logging is enabled.",
    )
    errorhandling_traceback: bool = Field(
        default=False,
        description="Include exception tracebacks in error responses.",
    )
    errorhandling_transform: bool = Field(
        default=True,
        description="Transform exceptions into MCP-friendly error responses.",
    )
    retry_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum retry attempts applied by retry middleware.",
    )
    retry_base_delay: float = Field(
        default=1.0,
        ge=0,
        description="Initial delay between retries in seconds.",
    )
    retry_max_delay: float = Field(
        default=60.0,
        ge=0,
        description="Upper bound on retry delay in seconds.",
    )
    retry_backoff_multiplier: float = Field(
        default=2.0,
        gt=0,
        description="Exponential backoff multiplier between retry attempts.",
    )
    cache_storage: str | None = Field(
        default=None,
        validation_alias=AliasChoices("cache_storage", "cache"),
        description=(
            "Storage backend for response caching: memory, null, file://, or redis://."
        ),
    )
    cache_ttl_sec: int = Field(
        default=3600,
        ge=0,
        validation_alias=AliasChoices("cache_ttl_sec", "cache_ttl_seconds"),
        description="TTL for cached tool responses (seconds).",
    )
    authz_policy_path: str | None = Field(
        default=None,
        description=(
            "Path to a Eunomia policy JSON file. When provided, the file must exist "
            "or the server will fail to start. When omitted, authorization middleware "
            "is disabled."
        ),
    )
    enable_audit_logging: bool = Field(
        default=True,
        description="Enable Eunomia audit logging when authorization middleware is active.",
    )
    fallback_behavior: Literal["fallback", "always"] | None = Field(
        default=None,
        description=(
            "Optional FastMCP sampling handler behavior ('fallback' or 'always'); "
            "set when providing a server-side sampling handler."
        ),
    )
    openai_api_key: str | None = Field(
        default=None,
        description="API key used by the OpenAI-compatible sampling fallback handler.",
    )
    openai_base_url: HttpUrl | None = Field(
        default=None,
        description="Optional base URL for OpenAI-compatible providers (e.g., LiteLLM proxy).",
    )
    openai_default_model: str | None = Field(
        default=None,
        description="Default model name used by the OpenAI sampling handler.",
    )

    @no_type_check
    def __init__(
        self,
        _env_file: str | Path | list[str | Path] | None = None,
        **data: object,
    ) -> None:
        # Delegate to BaseSettings while keeping _env_file visible to type checkers.
        super().__init__(_env_file=_env_file, **data)

    @model_validator(mode="after")
    def _apply_log_level_default(self) -> ServerSettings:
        if self.log_level is None:
            self.log_level = os.getenv("FASTMCP_LOG_LEVEL", "INFO")

        if self.cache_storage is None:
            self.cache_storage = os.getenv("POWERSEARCH_CACHE")

        cache_ttl = os.getenv("POWERSEARCH_CACHE_TTL_SEC") or os.getenv(
            "POWERSEARCH_CACHE_TTL_SECONDS"
        )
        if cache_ttl is not None:
            try:
                self.cache_ttl_sec = int(cache_ttl)
            except ValueError as exc:  # pragma: no cover - defensive guard
                raise ValueError(
                    "POWERSEARCH_CACHE_TTL_SEC must be an int"
                ) from exc
        return self

    @model_validator(mode="after")
    def _require_auth_when_authorization_enabled(self) -> ServerSettings:
        if self.authz_policy_path:
            auth_provider = os.getenv("FASTMCP_SERVER_AUTH", "").strip()

            if not auth_provider:
                raise ValueError(
                    "POWERSEARCH_AUTHZ_POLICY_PATH is set, but FASTMCP_SERVER_AUTH is not configured; enable authentication before enabling authorization."
                )

        return self

    def log_level_value(self) -> int:
        """Convert configured log level to a numeric value for logging APIs."""

        if isinstance(self.log_level, int):
            return self.log_level

        mapping = logging.getLevelNamesMapping()
        return mapping.get(str(self.log_level).upper(), logging.INFO)


def build_key_value_store(
    storage: str | None, *, default_collection: str | None = None
) -> AsyncKeyValue | None:
    """Construct an AsyncKeyValue backend from a shorthand string.

    Supported values:
    - None/empty/"none": returns None (caching disabled)
    The ``storage`` argument selects the backend implementation; the optional
    ``default_collection`` argument sets the name of the default collection
    for backends that support collections (MemoryStore, NullStore, DiskStore,
    RedisStore). For other values (including when caching is disabled), this
    parameter is ignored.

    Supported values for ``storage``:
    ``default_collection`` argument sets the name of the default collection
    for backends that support collections (MemoryStore, NullStore, DiskStore,
    RedisStore). For other values (including when caching is disabled), this
    parameter is ignored.

    Supported values for ``storage``:
    - "null": NullStore for side-effect-free testing
    - file://<path>: DiskStore rooted at the given path
    - redis://<host>:<port>/<db>: RedisStore
    """

    if storage is None:
        return None

    normalized = str(storage).strip()
    if not normalized or normalized.lower() == "none":
        return None

    lowered = normalized.lower()

    if lowered == "memory":
        return MemoryStore(default_collection=default_collection)

    if lowered == "null":
        return NullStore(
            default_collection=default_collection,
            stable_api=True,
        )

    if lowered.startswith("file://"):
        path_str = normalized[len("file://") :]
        if not path_str:
            raise ValueError(
                "POWERSEARCH_CACHE 'file://' storage requires a directory path"
            )
        directory = Path(path_str).expanduser()
        return DiskStore(
            directory=directory, default_collection=default_collection
        )

    if lowered.startswith("redis://"):
        return RedisStore(url=normalized, default_collection=default_collection)

    raise ValueError(
        f"Unsupported POWERSEARCH_CACHE value '{storage}'. Use memory, null, "
        "file://<path>, or redis://<host>:<port>/<db>."
    )


class Settings(BaseModel):
    """Aggregate settings for both server and search components."""

    powersearch: PowerSearchSettings = Field(
        default_factory=PowerSearchSettings
    )
    server: ServerSettings = Field(default_factory=ServerSettings)


settings = Settings()
powersearch_settings = settings.powersearch
server_settings = settings.server

__all__ = [
    "DEFAULT_BASE_URL",
    "PowerSearchSettings",
    "ServerSettings",
    "Settings",
    "build_key_value_store",
    "powersearch_settings",
    "server_settings",
    "settings",
]
