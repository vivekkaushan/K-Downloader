"""Entry point used by the launcher script and the packaged apps."""

from __future__ import annotations

import logging
import sys


def main() -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    from . import system
    if system.missing_modules():
        # Tk may still work; show a plain message rather than crashing silently.
        print("Missing components:", ", ".join(system.missing_modules()), file=sys.stderr)
    from .ui.app import KDownloaderApp
    app = KDownloaderApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
