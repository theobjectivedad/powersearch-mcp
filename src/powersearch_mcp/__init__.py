"""Agent Demo"""

import truststore

try:
    from ._version import version as __version__
except Exception:  # noqa: BLE001
    __version__ = "0.0.0+unknown"


import time

__all__ = ["__version__"]

# Trust system CA certificates
truststore.inject_into_ssl()
