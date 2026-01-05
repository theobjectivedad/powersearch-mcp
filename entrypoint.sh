#!/bin/sh
set -eu

# Derive the PowerSearch MCP search path
app_path=$(python - <<'PY'
import importlib.util
import pathlib

spec = importlib.util.find_spec("powersearch_mcp.app")
if spec is None or spec.origin is None:
    raise SystemExit("powersearch_mcp.app not found in site-packages")

print(pathlib.Path(spec.origin).resolve())
PY
)

exec fastmcp run "$app_path" --skip-env --skip-source "$@"
