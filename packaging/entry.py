"""PyInstaller entry point for the frozen ``plexget`` binary.

PyInstaller cannot freeze ``python -m plexget`` directly, so it targets this
tiny launcher, which just delegates to the real CLI entry point.
"""

import sys

from plexget.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
