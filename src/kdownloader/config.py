"""Persistent user settings (JSON, written atomically)."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Dict

from . import formats, paths

THEMES = ("dark", "light", "system")


@dataclass
class Settings:
    theme: str = "dark"
    download_dir: str = ""
    default_kind: str = formats.VIDEO
    default_video_quality: str = formats.DEFAULT_VIDEO_PRESET
    default_audio_quality: str = formats.DEFAULT_AUDIO_PRESET
    keep_history: bool = True
    max_history: int = 500

    def effective_download_dir(self) -> str:
        return self.download_dir or str(paths.default_download_dir())


def sanitize(data: Any) -> Settings:
    """Build valid Settings from arbitrary loaded data (unknown/bad values dropped)."""
    s = Settings()
    if not isinstance(data, dict):
        return s
    if data.get("theme") in THEMES:
        s.theme = data["theme"]
    if isinstance(data.get("download_dir"), str):
        s.download_dir = data["download_dir"].strip()
    if data.get("default_kind") in (formats.VIDEO, formats.AUDIO):
        s.default_kind = data["default_kind"]
    if formats.is_valid_preset(data.get("default_video_quality"), formats.VIDEO):
        s.default_video_quality = data["default_video_quality"]
    if formats.is_valid_preset(data.get("default_audio_quality"), formats.AUDIO):
        s.default_audio_quality = data["default_audio_quality"]
    if isinstance(data.get("keep_history"), bool):
        s.keep_history = data["keep_history"]
    mh = data.get("max_history")
    if isinstance(mh, int) and not isinstance(mh, bool) and 10 <= mh <= 5000:
        s.max_history = mh
    return s


class SettingsStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else paths.app_home() / "settings.json"

    def load(self) -> Settings:
        """Load settings. Never raises: a missing/corrupt file yields defaults."""
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return Settings()
        except OSError:
            return Settings()
        try:
            return sanitize(json.loads(raw))
        except ValueError:
            try:  # keep the unreadable file for inspection
                shutil.copyfile(self.path, self.path.with_suffix(".json.bad"))
            except OSError:
                pass
            return Settings()

    def save(self, settings: Settings) -> bool:
        return atomic_write_json(self.path, asdict(settings))

    def reset(self) -> Settings:
        s = Settings()
        self.save(s)
        return s


def atomic_write_json(path: Path, data: Any) -> bool:
    """Write JSON via a temp file + rename so a crash can't corrupt the file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return True
    except OSError:
        return False


# --- first-run welcome flag (same file/format as earlier versions) ---------

def _welcome_file() -> Path:
    return paths.app_home() / "welcome_acknowledged.json"


def welcome_seen() -> bool:
    try:
        return json.loads(_welcome_file().read_text(encoding="utf-8")).get("acknowledged") is True
    except (OSError, ValueError, AttributeError):
        return False


def mark_welcome_seen() -> None:
    atomic_write_json(_welcome_file(), {"acknowledged": True})
