#!/bin/sh
set -eu

transport=${TRANSPORT:-streamable-http}
host=${FASTMCP_HOST:-0.0.0.0}
port=${FASTMCP_PORT:-8099}
path_prefix=${FASTMCP_PATH:-/mcp}

# Allow extra CLI flags via FASTMCP_EXTRA_ARGS and runtime args.
set -- "$@"
if [ -n "${FASTMCP_EXTRA_ARGS:-}" ]; then
    set -- ${FASTMCP_EXTRA_ARGS} "$@"
fi

if [ "$transport" = "stdio" ]; then
    exec fastmcp run powersearch_mcp.app:mcp --skip-env --skip-source "$@"
fi

exec fastmcp run powersearch_mcp.app:mcp --skip-env --skip-source --transport "$transport" --host "$host" --port "$port" --path "$path_prefix" "$@"
