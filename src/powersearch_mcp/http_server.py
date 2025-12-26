"""Embedded HTTP server helpers for PowerSearch MCP."""

from __future__ import annotations

import contextlib
import io
import logging
import sys
from typing import cast

import uvicorn

from powersearch_mcp.powersearch import settings

from . import __version__
from .app import app, mcp

logger = logging.getLogger("powersearch-mcp")


class _NonClosingStreamHandler(logging.StreamHandler[io.TextIOBase]):
    """StreamHandler that does not close the underlying stream on shutdown."""

    def __init__(self, stream: io.TextIOBase) -> None:
        super().__init__(stream)

    def close(self) -> None:  # pragma: no cover - trivial
        self.flush()


def _prevent_handler_closure(handler: logging.Handler) -> None:
    """Ensure existing handlers do not close their underlying streams."""

    def _no_close() -> None:  # pragma: no cover - trivial
        with contextlib.suppress(Exception):
            handler.flush()

    handler.close = _no_close  # type: ignore[method-assign]


def run_stdio() -> None:
    """Start the MCP server over stdio (default)."""

    mcp.run(transport="stdio")


def run_http(  # noqa: PLR0913
    *,
    host: str,
    port: int,
    log_level: str,
    ssl_certfile: str | None,
    ssl_keyfile: str | None,
    ssl_keyfile_password: str | None,
    ssl_ca_certs: str | None,
    reload: bool,
) -> None:
    """Start the MCP server as an ASGI app under uvicorn."""

    log_level_value = getattr(logging, log_level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        stderr_stream = cast("io.TextIOBase", sys.__stderr__ or sys.stderr)
        new_handler = _NonClosingStreamHandler(stderr_stream)
        new_handler.setLevel(log_level_value)
        root_logger.addHandler(new_handler)
    else:
        for existing_handler in root_logger.handlers:
            _prevent_handler_closure(existing_handler)
    root_logger.setLevel(log_level_value)
    logger.setLevel(log_level_value)

    logger.info(
        "Starting Power Search HTTP server (version %s)",
        __version__,
    )
    logger.info(
        "Power Search configuration:\n%s", settings.model_dump_json(indent=2)
    )

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level.lower(),
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        ssl_keyfile_password=ssl_keyfile_password,
        ssl_ca_certs=ssl_ca_certs,
        reload=reload,
    )
