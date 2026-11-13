"""Filesystem locations. Nothing here is hard-coded to a particular user."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from .constants import CONFIG_DIR_NAME


def app_home() -> Path:
    """Folder for settings, history and the welcome flag (~/.k_downloader).

    ``KDOWNLOADER_HOME`` overrides it (used by tests).
    """
    override = os.environ.get("KDOWNLOADER_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / CONFIG_DIR_NAME


def default_download_dir() -> Path:
    return Path.home() / "Downloads" / "K Downloader"


def resource_path(name: str) -> Optional[Path]:
    """Locate a bundled resource (logo / icon).

    Order: PyInstaller bundle root, the ``src`` folder, the repository ``assets``
    folder (running from source).
    """
    here = Path(__file__).resolve().parent
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / name)
    candidates += [here.parent / name, here.parent.parent / "assets" / name]
    for path in candidates:
        if path.is_file():
            return path
    return None
