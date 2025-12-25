"""Agent Demo"""

import truststore

from ._version import version as __version__

__all__ = ["__version__"]

# Trust system CA certificates
truststore.inject_into_ssl()


# Adding a benign change to test to release 1.0.4
