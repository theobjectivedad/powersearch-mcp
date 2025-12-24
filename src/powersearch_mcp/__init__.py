"""Agent Demo"""

import truststore

from ._version import version as __version__

__all__ = ["__version__"]

# Trust system CA certificates
truststore.inject_into_ssl()
