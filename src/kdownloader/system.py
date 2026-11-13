"""OS-facing helpers: FFmpeg lookup, disk checks, opening folders, dependency checks."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

REQUIRED_MODULES = {
    "customtkinter": "CustomTkinter",
    "yt_dlp": "yt-dlp",
    "PIL": "Pillow",
    "imageio_ffmpeg": "imageio-ffmpeg",
}
PARTIAL_SUFFIXES = (".part", ".ytdl", ".temp", ".tmp")
MEDIA_EXTENSIONS = {
    ".mp4", ".mkv", ".webm", ".mov", ".m4a", ".mp3", ".opus", ".ogg", ".wav", ".flac", ".aac", ".m4v",
}


def missing_modules() -> List[str]:
    """Display names of required Python packages that cannot be imported."""
    return [name for mod, name in REQUIRED_MODULES.items() if importlib.util.find_spec(mod) is None]


def find_ffmpeg() -> Optional[str]:
    """Bundled FFmpeg (imageio-ffmpeg) first, then one on PATH. None if unavailable."""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.isfile(exe):
            return exe
    except Exception:
        pass
    return shutil.which("ffmpeg")


def ffmpeg_is_bundled(path: Optional[str]) -> bool:
    return bool(path) and "imageio_ffmpeg" in str(path)


def nearest_existing_parent(path: str | Path) -> Path:
    p = Path(path).expanduser()
    while not p.exists() and p != p.parent:
        p = p.parent
    return p


def free_space(path: str | Path) -> Optional[int]:
    try:
        return shutil.disk_usage(nearest_existing_parent(path)).free
    except OSError:
        return None


def prepare_folder(folder: str | Path, min_free: int) -> Tuple[bool, str]:
    """Make sure *folder* exists, is writable and has room. Returns (ok, message)."""
    folder = Path(folder).expanduser()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return False, (f"The download folder isn't available ({exc.strerror or exc}). "
                       "If it's on an external drive, check that the drive is connected.")
    try:
        with tempfile.NamedTemporaryFile(dir=str(folder), prefix=".kd_write_test_", delete=True):
            pass
    except OSError:
        return False, "K Downloader can't write to that folder. Choose a different download folder."
    free = free_space(folder)
    if free is not None and free < min_free:
        mb = free // (1024 * 1024)
        return False, f"Not enough free space in that folder ({mb} MB left). Free some space or choose another drive."
    return True, ""


def find_existing(folder: str | Path, video_id: str) -> Optional[str]:
    """A finished media file for *video_id* already in *folder* (never a partial)."""
    if not video_id:
        return None
    marker = f"[{video_id}]"
    try:
        with os.scandir(folder) as entries:
            for entry in entries:
                name = entry.name
                if marker in name and entry.is_file():
                    suffix = Path(name).suffix.lower()
                    if suffix in MEDIA_EXTENSIONS and not name.lower().endswith(PARTIAL_SUFFIXES):
                        return entry.path
    except OSError:
        return None
    return None


def cleanup_partials(folder: str | Path, video_id: str) -> int:
    """Delete leftover partial files of *video_id* (used after an explicit cancel)."""
    if not video_id:
        return 0
    marker = f"[{video_id}]"
    removed = 0
    try:
        with os.scandir(folder) as entries:
            doomed = [e.path for e in entries
                      if marker in e.name and e.is_file() and (
                          e.name.lower().endswith(PARTIAL_SUFFIXES) or ".part-" in e.name.lower()
                          or ".temp." in e.name.lower())]
    except OSError:
        return 0
    for path in doomed:
        try:
            os.unlink(path)
            removed += 1
        except OSError:
            pass
    return removed


def open_path(path: str | Path) -> bool:
    """Open a folder (or reveal a file) in the system file manager."""
    p = Path(path).expanduser()
    try:
        if sys.platform == "darwin":
            if p.is_file():
                subprocess.Popen(["open", "-R", str(p)])
            else:
                subprocess.Popen(["open", str(p)])
        elif sys.platform.startswith("win"):
            if p.is_file():
                subprocess.Popen(["explorer", "/select,", str(p)])
            else:
                os.startfile(str(p))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(p if p.is_dir() else p.parent)])
        return True
    except (OSError, ValueError):
        return False
