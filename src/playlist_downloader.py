#!/usr/bin/env python3
"""K Downloader launcher (KAUSHAN). The application lives in the ``kdownloader`` package."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from kdownloader.app_main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
