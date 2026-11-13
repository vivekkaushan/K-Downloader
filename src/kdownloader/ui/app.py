"""Main window: sidebar navigation, page container and footer."""

from __future__ import annotations

import logging
import sys

import customtkinter as ctk

from .. import system
from ..config import SettingsStore
from ..constants import APP_NAME, MIN_FREE_BYTES, __version__
from ..engine import DownloadManager, Status
from ..history import HistoryStore
from . import dialogs, theme, widgets
from .context import AppContext, Dispatcher
from .pages.about import AboutPage
from .pages.dashboard import DashboardPage
from .pages.history import HistoryPage
from .pages.playlist import PlaylistPage
from .pages.settings import SettingsPage
from .pages.single import SingleVideoPage
from .welcome import show_if_first_run

log = logging.getLogger("kdownloader")

NAV = [("dashboard", "Dashboard", DashboardPage), ("playlist", "Playlist Downloader", PlaylistPage),
       ("single", "Single Video", SingleVideoPage), ("history", "Download History", HistoryPage),
       ("settings", "Settings", SettingsPage), ("about", "About K Downloader", AboutPage)]


class KDownloaderApp(ctk.CTk):
    def __init__(self, store: SettingsStore = None, history: HistoryStore = None, show_welcome: bool = True):
        store = store or SettingsStore()
        settings = store.load()
        theme.apply_mode(settings.theme)
        super().__init__(fg_color=theme.BG)
        self.title(f"{APP_NAME} — KAUSHAN")
        self.geometry("1180x780")
        self.minsize(980, 660)
        self._set_icon()

        self.dispatcher = Dispatcher(self)
        history = history or HistoryStore(max_items=settings.max_history)
        history.set_max(settings.max_history)
        ffmpeg = system.find_ffmpeg()
        manager = DownloadManager(lambda kind, payload: self.dispatcher.post(self._on_event, kind, payload),
                                  ffmpeg_path=ffmpeg, min_free_bytes=MIN_FREE_BYTES,
                                  parallel=settings.parallel_downloads)
        self.ctx = AppContext(self, store, settings, history, manager, self.dispatcher, ffmpeg)
        self.ctx.navigate = self.show_page
        self.ctx.settings_changed = self._settings_changed
        self.ctx.theme_changed = self._theme_changed

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=24, pady=(20, 0))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)
        for key, _, cls in NAV:
            page = cls(self.content, self.ctx)
            page.grid(row=0, column=0, sticky="nsew")
            self.ctx.pages[key] = page
        widgets.Footer(self, __version__).grid(row=1, column=1, sticky="ew", padx=24, pady=(4, 8))

        self.current = ""
        self.show_page("dashboard")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.dispatcher.start()
        self.after(400, self._startup_checks)
        if show_welcome:
            self.after(700, lambda: show_if_first_run(self))

    # -- construction ---------------------------------------------------------

    def _set_icon(self) -> None:
        try:
            from .. import paths
            from ..constants import ICON_FILE
            ico = paths.resource_path(ICON_FILE)
            if ico and sys.platform.startswith("win"):
                self.iconbitmap(str(ico))
            else:
                from PIL import ImageTk, Image
                logo = paths.resource_path("k_downloader_logo.png")
                if logo:
                    self._icon = ImageTk.PhotoImage(Image.open(logo).convert("RGBA").resize((128, 128)))
                    self.iconphoto(True, self._icon)
        except Exception:
            log.debug("Could not set the window icon", exc_info=True)

    def _build_sidebar(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=theme.SIDEBAR, corner_radius=0, width=228)
        bar.grid(row=0, column=0, rowspan=2, sticky="nsw")
        bar.grid_propagate(False)
        logo = widgets.logo_image(44)
        head = ctk.CTkFrame(bar, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(22, 20))
        ctk.CTkLabel(head, text="" if logo else "K", image=logo).pack(side="left")
        col = ctk.CTkFrame(head, fg_color="transparent")
        col.pack(side="left", padx=10)
        widgets.label(col, "K Downloader", 15, "bold").pack(anchor="w")
        widgets.label(col, "KAUSHAN", 10, "bold", theme.ACCENT).pack(anchor="w")
        self.nav_buttons = {}
        for key, text, _ in NAV:
            btn = ctk.CTkButton(bar, text=text, anchor="w", height=40, corner_radius=10, font=theme.font(13),
                                fg_color="transparent", hover_color=theme.SURFACE_HOVER, text_color=theme.TEXT,
                                command=lambda k=key: self.show_page(k))
            btn.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[key] = btn
        self.side_note = widgets.muted(bar, "", 11, wraplength=190, justify="left", anchor="w")
        self.side_note.pack(side="bottom", anchor="w", padx=18, pady=16)

    # -- behaviour --------------------------------------------------------------

    def show_page(self, key: str) -> None:
        if key not in self.ctx.pages:
            return
        for k, btn in self.nav_buttons.items():
            btn.configure(fg_color=theme.SELECTED if k == key else "transparent",
                          text_color=theme.ACCENT if k == key else theme.TEXT)
        page = self.ctx.pages[key]
        page.tkraise()
        self.current = key
        page.on_show()

    def _on_event(self, kind: str, payload) -> None:
        if kind == "finished" and self.ctx.settings.keep_history:
            self._record(payload)
        for page in self.ctx.pages.values():
            try:
                page.on_engine_event(kind, payload)
            except Exception:
                log.exception("Page failed to handle an event")
        if kind in ("added", "finished", "idle", "removed"):
            self._update_side_note()

    def _record(self, item) -> None:
        if item.status == Status.CANCELLED:
            return
        self.ctx.history.add({"video_id": item.video_id, "title": item.title, "url": item.url, "status": item.status,
                              "preset": item.preset_id, "size": item.size, "filepath": item.filepath,
                              "dest_dir": item.dest_dir, "source": item.source, "error": item.error})

    def _update_side_note(self) -> None:
        s = self.ctx.manager.stats()
        busy = s["queued"] + s["active"]
        self.side_note.configure(text=f"{busy} download(s) in progress" if busy else "")

    def _settings_changed(self) -> None:
        self.ctx.manager.set_parallel(self.ctx.settings.parallel_downloads)
        for page in self.ctx.pages.values():
            page.on_settings_changed()

    def _theme_changed(self) -> None:
        self.configure(fg_color=theme.BG)
        for page in self.ctx.pages.values():
            for lst in _find_lists(page):
                lst.refresh()
        self.show_page(self.current)

    def _startup_checks(self) -> None:
        missing = system.missing_modules()
        if missing:
            dialogs.notify(self, "Missing components", "These components are missing: " + ", ".join(missing) +
                           ". Please reinstall K Downloader.")
        elif not self.ctx.ffmpeg_ok:
            self.ctx.pages["dashboard"].prog_text.configure(
                text="FFmpeg wasn't found, so MP3 conversion and some quality options are unavailable.")

    def _on_close(self) -> None:
        s = self.ctx.manager.stats()
        if s["queued"] + s["active"]:
            if not dialogs.ask(self, "Downloads in progress", "Closing now will stop your downloads. Partial files are kept "
                               "so they can resume next time.", ok="Quit", cancel="Keep downloading", danger=True):
                return
        self.dispatcher.stop()
        try:
            self.ctx.manager.shutdown()
        finally:
            self.destroy()


def _find_lists(widget):
    from .virtual_list import VirtualList
    out = []
    for child in widget.winfo_children():
        if isinstance(child, VirtualList):
            out.append(child)
        out.extend(_find_lists(child))
    return out
