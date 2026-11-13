"""Download engine: playlist/video lookup and a threaded download queue.

This module has no GUI imports. The queue reports progress through an ``emit``
callback (``emit(kind, payload)``) that must be thread-safe and non-blocking; the
GUI passes a function that posts onto its own event loop.

Events
------
``"added"``     payload: DownloadItem snapshot (item entered the queue)
``"progress"``  payload: DownloadItem snapshot (status/progress changed)
``"finished"``  payload: DownloadItem snapshot (Completed/Failed/Cancelled/Already saved)
``"removed"``   payload: list of item ids dropped from the queue
``"idle"``      payload: summary dict (worker ran out of queued items)
"""

from __future__ import annotations

import dataclasses
import os
import threading
import time
import urllib.request
import uuid
from collections import deque
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import yt_dlp
from yt_dlp.utils import DownloadCancelled

from . import formats, system
from .constants import MIN_FREE_BYTES
from .errors import FriendlyError, classify_error


class Status:
    QUEUED = "Queued"
    DOWNLOADING = "Downloading"
    PROCESSING = "Processing"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    SKIPPED = "Already saved"

    TERMINAL = (COMPLETED, FAILED, CANCELLED, SKIPPED)
    ACTIVE = (DOWNLOADING, PROCESSING)


class Cancelled(DownloadCancelled):
    """Raised from inside yt-dlp hooks to abort the current download."""


class FetchError(Exception):
    def __init__(self, friendly: FriendlyError):
        super().__init__(friendly.message)
        self.friendly = friendly


@dataclass
class EntryInfo:
    video_id: str
    title: str
    url: str
    duration: Optional[float] = None
    thumbnail_url: Optional[str] = None
    uploader: Optional[str] = None


@dataclass
class PlaylistInfo:
    url: str
    title: str
    uploader: Optional[str]
    thumbnail_url: Optional[str]
    entries: List[EntryInfo]
    unavailable: int = 0


@dataclass
class DownloadItem:
    video_id: str
    title: str
    url: str
    preset_id: str
    dest_dir: str
    source: str = "playlist"          # "playlist" | "single"
    batch_id: str = ""
    duration: Optional[float] = None
    thumbnail_url: Optional[str] = None
    id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    status: str = Status.QUEUED
    progress: float = 0.0
    speed: Optional[float] = None
    eta: Optional[float] = None
    downloaded: int = 0
    total: int = 0
    error: str = ""
    error_code: str = ""
    retryable: bool = False
    filepath: str = ""
    size: int = 0
    note: str = ""
    queued_at: float = dataclasses.field(default_factory=time.time)
    started_at: float = 0.0
    finished_at: float = 0.0

    @property
    def is_terminal(self) -> bool:
        return self.status in Status.TERMINAL


def new_item(entry: EntryInfo, preset_id: str, dest_dir: str, source: str, batch_id: str = "") -> DownloadItem:
    return DownloadItem(video_id=entry.video_id, title=entry.title, url=entry.url, preset_id=preset_id,
                        dest_dir=dest_dir, source=source, batch_id=batch_id, duration=entry.duration,
                        thumbnail_url=entry.thumbnail_url)


# ---------------------------------------------------------------------------
# Looking up playlists and videos
# ---------------------------------------------------------------------------

_UNAVAILABLE_TITLES = {"[private video]", "[deleted video]", "[unavailable video]"}


def _pick_thumbnail(info: dict) -> Optional[str]:
    if info.get("thumbnail"):
        return info["thumbnail"]
    thumbs = [t.get("url") for t in (info.get("thumbnails") or []) if isinstance(t, dict) and t.get("url")]
    return thumbs[-1] if thumbs else None


def _entry_url(item: dict) -> Optional[str]:
    link = item.get("webpage_url") or item.get("url")
    if link and str(link).startswith(("http://", "https://")):
        return str(link)
    vid = item.get("id")
    return f"https://www.youtube.com/watch?v={vid}" if vid else None


def _fetch_opts(**extra) -> dict:
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "socket_timeout": 20,
            "ignoreerrors": False}
    opts.update(extra)
    return opts


def fetch_playlist(url: str, ydl_factory: Callable = yt_dlp.YoutubeDL) -> PlaylistInfo:
    """Read a playlist's title and videos without downloading anything."""
    try:
        with ydl_factory(_fetch_opts(extract_flat="in_playlist")) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # yt-dlp raises DownloadError / ExtractorError / OSError
        raise FetchError(classify_error(exc)) from exc
    if not info:
        raise FetchError(FriendlyError("empty", "Nothing could be read from that link."))
    raw_entries = info.get("entries")
    if raw_entries is None:
        raise FetchError(FriendlyError(
            "not_playlist", "That link points to a single video, not a playlist. "
                            "Use the Single Video Downloader page for it."))
    entries: List[EntryInfo] = []
    unavailable = 0
    seen = set()
    for item in raw_entries:
        if not item:
            unavailable += 1
            continue
        title = (item.get("title") or "").strip()
        link = _entry_url(item)
        if not link or title.lower() in _UNAVAILABLE_TITLES:
            unavailable += 1
            continue
        vid = str(item.get("id") or "")
        key = vid or link
        if key in seen:
            continue
        seen.add(key)
        thumb = _pick_thumbnail(item)
        if not thumb and vid and "youtube.com" in link:
            thumb = f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
        entries.append(EntryInfo(video_id=vid, title=title or "Untitled video", url=link,
                                 duration=item.get("duration"), thumbnail_url=thumb,
                                 uploader=item.get("uploader") or item.get("channel")))
    if not entries:
        raise FetchError(FriendlyError(
            "empty", "No downloadable videos were found. The playlist may be empty, private or unavailable."))
    return PlaylistInfo(
        url=url, title=(info.get("title") or "Playlist").strip(),
        uploader=info.get("uploader") or info.get("channel") or entries[0].uploader,
        thumbnail_url=_pick_thumbnail(info) or entries[0].thumbnail_url,
        entries=entries, unavailable=unavailable)


def fetch_video(url: str, ydl_factory: Callable = yt_dlp.YoutubeDL) -> EntryInfo:
    """Read one video's details without downloading it."""
    try:
        with ydl_factory(_fetch_opts(noplaylist=True)) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise FetchError(classify_error(exc)) from exc
    if not info or info.get("entries") is not None:
        raise FetchError(FriendlyError("invalid_url", "That link doesn't point to a single downloadable video."))
    if info.get("is_live"):
        raise FetchError(classify_error("live stream"))
    link = info.get("webpage_url") or url
    return EntryInfo(video_id=str(info.get("id") or ""), title=(info.get("title") or "Untitled video").strip(),
                     url=link, duration=info.get("duration"), thumbnail_url=_pick_thumbnail(info),
                     uploader=info.get("uploader") or info.get("channel"))


def fetch_thumbnail(url: Optional[str], timeout: float = 8.0, limit: int = 3_000_000) -> Optional[bytes]:
    """Download a small preview image. Returns None on any problem."""
    if not url or not str(url).startswith("https://"):
        return None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "K-Downloader"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec - https only
            data = resp.read(limit + 1)
        return data if 0 < len(data) <= limit else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def summarize(items: Iterable[DownloadItem]) -> Dict[str, object]:
    items = list(items)
    count = lambda *s: sum(1 for i in items if i.status in s)  # noqa: E731
    total = len(items)
    terminal = sum(1 for i in items if i.is_terminal)
    in_flight = sum(i.progress for i in items if not i.is_terminal)
    progress = (terminal + in_flight) / total if total else 0.0
    active = [i for i in items if i.status in Status.ACTIVE]
    queued = count(Status.QUEUED)
    speed = sum(i.speed or 0 for i in active) or None
    done_times = [i.finished_at - i.started_at for i in items
                  if i.status == Status.COMPLETED and i.finished_at and i.started_at]
    avg = sum(done_times) / len(done_times) if done_times else None
    current_eta = max((i.eta for i in active if i.eta is not None), default=None)
    eta: Optional[float] = None
    if active or queued:
        if avg is not None:
            eta = (current_eta if current_eta is not None else avg / 2) + queued * avg
        elif queued == 0:
            eta = current_eta
    return {
        "total": total, "queued": queued, "active": len(active),
        "completed": count(Status.COMPLETED), "failed": count(Status.FAILED),
        "cancelled": count(Status.CANCELLED), "skipped": count(Status.SKIPPED),
        "finished": terminal, "progress": min(1.0, progress), "speed": speed, "eta": eta,
    }


# ---------------------------------------------------------------------------
# The download queue
# ---------------------------------------------------------------------------

class _QuietLogger:
    """Keeps yt-dlp from printing (there may be no console in a windowed app)."""

    def debug(self, msg): pass
    def info(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


class _Failure(Exception):
    def __init__(self, friendly: FriendlyError):
        super().__init__(friendly.message)
        self.friendly = friendly


class DownloadManager:
    """Runs downloads one at a time on a background thread.

    The worker thread exists only while there is work, so an idle app has no
    background activity.
    """

    PROGRESS_INTERVAL = 0.2

    def __init__(self, emit: Callable[[str, object], None], ffmpeg_path: Optional[str] = None,
                 ydl_factory: Optional[Callable] = None, min_free_bytes: int = MIN_FREE_BYTES,
                 retry_delays: Tuple[float, ...] = (3.0, 8.0)):
        self._emit = emit
        self.ffmpeg_path = ffmpeg_path
        self._ydl_factory = ydl_factory or yt_dlp.YoutubeDL
        self._min_free = min_free_bytes
        self._retry_delays = retry_delays
        self._lock = threading.RLock()
        self._items: Dict[str, DownloadItem] = {}
        self._queue: deque = deque()
        self._current_id: Optional[str] = None
        self._item_cancel = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # -- public API -------------------------------------------------------

    def enqueue(self, items: Iterable[DownloadItem]) -> Tuple[List[DownloadItem], int]:
        """Queue items. Returns (accepted, number_skipped_as_duplicates)."""
        accepted: List[DownloadItem] = []
        duplicates = 0
        with self._lock:
            for item in items:
                if self._is_duplicate(item):
                    duplicates += 1
                    continue
                item.status = Status.QUEUED
                item.queued_at = time.time()
                self._items[item.id] = item
                self._queue.append(item.id)
                accepted.append(item)
                self._emit("added", dataclasses.replace(item))
            if accepted:
                self._ensure_worker()
        return accepted, duplicates

    def cancel(self, item_id: str) -> None:
        with self._lock:
            item = self._items.get(item_id)
            if not item:
                return
            if item.status == Status.QUEUED:
                try:
                    self._queue.remove(item_id)
                except ValueError:
                    pass
                self._finish(item, Status.CANCELLED)
            elif item_id == self._current_id and item.status in Status.ACTIVE:
                self._item_cancel.set()

    def stop_all(self) -> None:
        with self._lock:
            while self._queue:
                item = self._items.get(self._queue.popleft())
                if item and item.status == Status.QUEUED:
                    self._finish(item, Status.CANCELLED)
            if self._current_id:
                self._item_cancel.set()

    def retry(self, item_ids: Optional[Iterable[str]] = None) -> int:
        """Re-queue Failed/Cancelled items (all of them when *item_ids* is None)."""
        count = 0
        with self._lock:
            ids = list(item_ids) if item_ids is not None else list(self._items)
            for item_id in ids:
                item = self._items.get(item_id)
                if not item or item.status not in (Status.FAILED, Status.CANCELLED):
                    continue
                item.status = Status.QUEUED
                item.progress, item.speed, item.eta = 0.0, None, None
                item.downloaded = item.total = 0
                item.error = item.error_code = item.note = ""
                item.started_at = item.finished_at = 0.0
                self._queue.append(item_id)
                count += 1
                self._emit("progress", dataclasses.replace(item))
            if count:
                self._ensure_worker()
        return count

    def remove(self, item_ids: Iterable[str]) -> None:
        """Forget finished items (active/queued ones are left alone)."""
        removed = []
        with self._lock:
            for item_id in item_ids:
                item = self._items.get(item_id)
                if item and item.is_terminal:
                    del self._items[item_id]
                    removed.append(item_id)
        if removed:
            self._emit("removed", removed)

    def clear_finished(self) -> None:
        with self._lock:
            ids = [i.id for i in self._items.values() if i.is_terminal]
        self.remove(ids)

    def snapshot(self) -> List[DownloadItem]:
        with self._lock:
            return [dataclasses.replace(i) for i in self._items.values()]

    def get(self, item_id: str) -> Optional[DownloadItem]:
        with self._lock:
            item = self._items.get(item_id)
            return dataclasses.replace(item) if item else None

    def is_active(self) -> bool:
        with self._lock:
            return bool(self._queue) or self._current_id is not None

    def stats(self) -> Dict[str, object]:
        return summarize(self.snapshot())

    def shutdown(self, timeout: float = 5.0) -> None:
        self.stop_all()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout)

    def wait_idle(self, timeout: float = 30.0) -> bool:
        """Block until the worker has finished (used by tests)."""
        thread = self._thread
        if thread:
            thread.join(timeout)
        return not self.is_active()

    # -- internals --------------------------------------------------------

    def _is_duplicate(self, item: DownloadItem) -> bool:
        for other in self._items.values():
            if (other.status in (Status.QUEUED,) + Status.ACTIVE and other.video_id == item.video_id
                    and other.url == item.url and other.preset_id == item.preset_id
                    and other.dest_dir == item.dest_dir):
                return True
        return False

    def _ensure_worker(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="kd-downloads", daemon=True)
            self._thread.start()

    def _run(self) -> None:
        while True:
            with self._lock:
                item = None
                while self._queue:
                    candidate = self._items.get(self._queue.popleft())
                    if candidate and candidate.status == Status.QUEUED:
                        item = candidate
                        break
                if item is None:
                    self._thread = None
                    break
                self._current_id = item.id
                self._item_cancel.clear()
                item.status = Status.DOWNLOADING
                item.started_at = time.time()
                self._emit("progress", dataclasses.replace(item))
            try:
                self._process(item)
            except Exception as exc:  # never let the worker die silently
                self._finish_locked(item, Status.FAILED, friendly=classify_error(exc))
            finally:
                with self._lock:
                    self._current_id = None
        self._emit("idle", self.stats())

    def _finish_locked(self, item: DownloadItem, status: str, friendly: Optional[FriendlyError] = None,
                       filepath: str = "") -> None:
        with self._lock:
            self._finish(item, status, friendly, filepath)

    def _finish(self, item: DownloadItem, status: str, friendly: Optional[FriendlyError] = None,
                filepath: str = "") -> None:
        item.status = status
        item.finished_at = time.time()
        item.speed = item.eta = None
        item.note = ""
        if status in (Status.COMPLETED, Status.SKIPPED):
            item.progress = 1.0
            item.filepath = filepath
            try:
                item.size = os.path.getsize(filepath) if filepath else 0
            except OSError:
                item.size = 0
        if friendly:
            item.error, item.error_code, item.retryable = friendly.message, friendly.code, friendly.retryable
        self._emit("finished", dataclasses.replace(item))

    def _update(self, item: DownloadItem, **fields) -> None:
        with self._lock:
            for key, value in fields.items():
                setattr(item, key, value)
            self._emit("progress", dataclasses.replace(item))

    def _process(self, item: DownloadItem) -> None:
        ok, message = system.prepare_folder(item.dest_dir, self._min_free)
        if not ok:
            code = "disk_full" if "free space" in message else "folder"
            self._finish_locked(item, Status.FAILED, friendly=FriendlyError(code, message))
            return
        existing = system.find_existing(item.dest_dir, item.video_id)
        if existing:
            self._finish_locked(item, Status.SKIPPED, filepath=existing)
            return
        attempt = 0
        while True:
            try:
                path = self._download_once(item)
                self._finish_locked(item, Status.COMPLETED, filepath=path)
                return
            except Exception as exc:
                if self._item_cancel.is_set() or isinstance(exc, Cancelled):
                    system.cleanup_partials(item.dest_dir, item.video_id)
                    self._finish_locked(item, Status.CANCELLED)
                    return
                friendly = classify_error(exc)
                if friendly.retryable and attempt < len(self._retry_delays):
                    delay = self._retry_delays[attempt]
                    attempt += 1
                    self._update(item, status=Status.DOWNLOADING, speed=None, eta=None,
                                 note=f"Connection problem — retrying ({attempt}/{len(self._retry_delays)})")
                    if self._item_cancel.wait(delay):
                        system.cleanup_partials(item.dest_dir, item.video_id)
                        self._finish_locked(item, Status.CANCELLED)
                        return
                    continue
                self._finish_locked(item, Status.FAILED, friendly=friendly)
                return

    def _download_once(self, item: DownloadItem) -> str:
        preset = formats.get_preset(item.preset_id)
        state = {"stream": 0, "streams": 1, "last_emit": 0.0}

        def hook(data: dict) -> None:
            if self._item_cancel.is_set():
                raise Cancelled("Stopped by user")
            requested = (data.get("info_dict") or {}).get("requested_formats")
            if requested:
                state["streams"] = max(1, len(requested))
            status = data.get("status")
            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate") or 0
                done = data.get("downloaded_bytes") or 0
                fraction = min(1.0, done / total) if total else 0.0
                overall = (state["stream"] + fraction) / state["streams"]
                now = time.monotonic()
                if now - state["last_emit"] < self.PROGRESS_INTERVAL:
                    return
                state["last_emit"] = now
                self._update(item, status=Status.DOWNLOADING, progress=max(item.progress, min(overall, 0.99)),
                             speed=data.get("speed"), eta=data.get("eta"), downloaded=done, total=total, note="")
            elif status == "finished":
                state["stream"] += 1
                if state["stream"] >= state["streams"]:
                    self._update(item, status=Status.PROCESSING, progress=0.99, speed=None, eta=None)

        def pp_hook(data: dict) -> None:
            if self._item_cancel.is_set():
                raise Cancelled("Stopped by user")
            if data.get("status") == "started" and item.status != Status.PROCESSING:
                self._update(item, status=Status.PROCESSING, speed=None, eta=None)

        opts = {
            "outtmpl": os.path.join(item.dest_dir, "%(title).180B [%(id)s].%(ext)s"),
            "noplaylist": True, "continuedl": True, "overwrites": False, "windowsfilenames": True,
            "retries": 5, "fragment_retries": 5, "socket_timeout": 20, "ignoreerrors": False,
            "quiet": True, "no_warnings": True, "noprogress": True, "logger": _QuietLogger(),
            "progress_hooks": [hook], "postprocessor_hooks": [pp_hook],
        }
        opts.update(formats.build_options(preset, self.ffmpeg_path))
        with self._ydl_factory(opts) as ydl:
            info = ydl.extract_info(item.url, download=True)
            path = self._resolve_path(info, item)
        if not path:
            raise RuntimeError("The download finished but the file could not be found.")
        return path

    @staticmethod
    def _resolve_path(info: Optional[dict], item: DownloadItem) -> str:
        for entry in (info or {}).get("requested_downloads") or []:
            fp = entry.get("filepath")
            if fp and os.path.isfile(fp):
                return fp
        return system.find_existing(item.dest_dir, item.video_id) or ""
