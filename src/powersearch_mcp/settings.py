"""Configuration models for PowerSearch MCP server and core search logic."""

from __future__ import annotations

import logging
import os
from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    TypeAdapter,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_BASE_URL: HttpUrl = TypeAdapter(HttpUrl).validate_python(
    "http://127.0.0.1:9876"
)


class PowerSearchSettings(BaseSettings):
    """Runtime configuration for Power Search sourced from environment."""

    model_config = SettingsConfigDict(
        env_prefix="POWERSEARCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
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
        default=4000,
        ge=0,
        description="Trim each result's content to this many characters; None to disable.",
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
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    log_level: str | int | None = Field(
        default=None,
        description=(
            "Logging level for middleware; defaults to FASTMCP_LOG_LEVEL or INFO."
        ),
    )
    include_payloads: bool = Field(
        default=False,
        description="Include MCP request/response payload bodies in logs.",
    )
    include_payload_length: bool = Field(
        default=False,
        description="Log payload length alongside other request metadata.",
    )
    estimate_payload_tokens: bool = Field(
        default=False,
        description="Estimate token counts (length // 4) when logging payloads.",
    )
    max_payload_length: int = Field(
        default=1000,
        ge=0,
        description="Maximum payload characters to log when payload logging is enabled.",
    )

    @model_validator(mode="after")
    def _apply_log_level_default(self) -> ServerSettings:
        if self.log_level is None:
            self.log_level = os.getenv("FASTMCP_LOG_LEVEL", "INFO")
        return self

    def log_level_value(self) -> int:
        """Convert configured log level to a numeric value for logging APIs."""

        if isinstance(self.log_level, int):
            return self.log_level

        mapping = logging.getLevelNamesMapping()
        return mapping.get(str(self.log_level).upper(), logging.INFO)


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
    "powersearch_settings",
    "server_settings",
    "settings",
]
