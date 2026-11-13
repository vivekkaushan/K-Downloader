"""Shared application state handed to every page, plus thread-safe UI dispatch."""

from __future__ import annotations

import logging
import queue
import threading
from typing import Callable, List, Optional

from .. import formats
from ..config import Settings, SettingsStore
from ..engine import DownloadManager
from ..history import HistoryStore

log = logging.getLogger("kdownloader")


class Dispatcher:
    """Lets worker threads schedule calls on the Tk main thread.

    Worker threads only ever call :meth:`post`; the main thread drains the queue
    on a short timer, so widgets are never touched from another thread.
    """

    INTERVAL_MS = 40

    def __init__(self, root):
        self.root = root
        self._queue: "queue.Queue" = queue.Queue()
        self._after_id = None
        self._closed = False

    def post(self, fn: Callable, *args) -> None:
        self._queue.put((fn, args))

    def run_async(self, work: Callable, done: Callable) -> None:
        """Run ``work()`` on a thread, then call ``done(result, error)`` on the UI thread."""
        def target():
            try:
                result, error = work(), None
            except Exception as exc:  # reported to the UI, never lost
                result, error = None, exc
            self.post(done, result, error)
        threading.Thread(target=target, name="kd-task", daemon=True).start()

    def start(self) -> None:
        self._pump()

    def stop(self) -> None:
        self._closed = True
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass

    def _pump(self) -> None:
        if self._closed:
            return
        for _ in range(300):
            try:
                fn, args = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn(*args)
            except Exception:
                log.exception("Error while handling a UI event")
        try:
            self._after_id = self.root.after(self.INTERVAL_MS, self._pump)
        except Exception:
            self._closed = True


class AppContext:
    def __init__(self, root, settings_store: SettingsStore, settings: Settings, history: HistoryStore,
                 manager: DownloadManager, dispatcher: Dispatcher, ffmpeg_path: Optional[str]):
        self.root = root
        self.settings_store = settings_store
        self.settings = settings
        self.history = history
        self.manager = manager
        self.dispatcher = dispatcher
        self.ffmpeg_path = ffmpeg_path
        self.navigate: Callable[[str], None] = lambda page: None
        self.settings_changed: Callable[[], None] = lambda: None
        self.theme_changed: Callable[[], None] = lambda: None
        self.pages: dict = {}

    @property
    def ffmpeg_ok(self) -> bool:
        return bool(self.ffmpeg_path)

    def presets(self, kind: str) -> List[formats.FormatPreset]:
        return formats.presets_for(kind, self.ffmpeg_ok)

    def save_settings(self) -> None:
        self.settings_store.save(self.settings)

    def run_async(self, work: Callable, done: Callable) -> None:
        self.dispatcher.run_async(work, done)
