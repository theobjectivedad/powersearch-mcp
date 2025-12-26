"""CLI entrypoint for PowerSearch MCP in stdio or HTTP modes."""

from __future__ import annotations

import click

from .http_server import run_http, run_stdio

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8092
DEFAULT_LOG_LEVEL = "info"


@click.command(context_settings={"auto_envvar_prefix": "POWERSEARCH_HTTP"})
@click.option(
    "--transport",
    type=click.Choice(["stdio", "http"], case_sensitive=False),
    default="stdio",
    show_default=True,
    help="Transport to launch (stdio or HTTP).",
)
@click.option(
    "--host",
    default=DEFAULT_HOST,
    show_default=True,
    help="Host interface for HTTP transport.",
)
@click.option(
    "--port",
    type=int,
    default=DEFAULT_PORT,
    show_default=True,
    help="Port for HTTP transport.",
)
@click.option(
    "--log-level",
    default=DEFAULT_LOG_LEVEL,
    show_default=True,
    type=click.Choice(
        ["critical", "error", "warning", "info", "debug", "trace"],
        case_sensitive=False,
    ),
    help="Log level for uvicorn in HTTP mode.",
)
@click.option(
    "--ssl-certfile",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="PEM-encoded certificate file to enable HTTPS.",
)
@click.option(
    "--ssl-keyfile",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="PEM-encoded private key file to enable HTTPS.",
)
@click.option(
    "--ssl-keyfile-password",
    help="Password for the TLS private key, if encrypted.",
)
@click.option(
    "--ssl-ca-certs",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help="Optional CA bundle for client verification.",
)
@click.option(
    "--reload/--no-reload",
    default=False,
    show_default=True,
    help="Enable uvicorn reload (development only).",
)
def cli(  # noqa: PLR0913
    *,
    transport: str,
    host: str,
    port: int,
    log_level: str,
    ssl_certfile: str | None,
    ssl_keyfile: str | None,
    ssl_keyfile_password: str | None,
    ssl_ca_certs: str | None,
    reload: bool,
) -> None:
    """Launch PowerSearch MCP over stdio or HTTP."""

    if (ssl_certfile and not ssl_keyfile) or (ssl_keyfile and not ssl_certfile):
        msg = "Both --ssl-certfile and --ssl-keyfile are required to enable HTTPS."
        raise click.BadParameter(msg)

    transport_choice = transport.lower()

    if transport_choice == "stdio":
        run_stdio()
        return

    run_http(
        host=host,
        port=port,
        log_level=log_level,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        ssl_keyfile_password=ssl_keyfile_password,
        ssl_ca_certs=ssl_ca_certs,
        reload=reload,
    )


def main() -> None:
    cli(standalone_mode=True)


if __name__ == "__main__":
    main()
