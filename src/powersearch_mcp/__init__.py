"""Agent Demo"""

import truststore

from powersearch_mcp.settings import (
    powersearch_settings,
    server_settings,
    settings,
)

try:
    from ._version import version as __version__
except Exception:  # noqa: BLE001
    __version__ = "0.0.0+unknown"


__all__ = [
    "__version__",
    "powersearch_settings",
    "server_settings",
    "settings",
]

# Trust system CA certificates
truststore.inject_into_ssl()
