from __future__ import annotations

from typing import Dict, List, Optional, Set

import customtkinter as ctk

from ... import urls
from ...engine import (EntryInfo, FetchError, PlaylistInfo, Status, fetch_playlist, fetch_thumbnail, new_item)
from ...utils import format_duration
from .. import dialogs, theme, widgets
from ..pickers import FolderPicker, FormatPicker
from ..queue_view import QueueView, item_row
from ..virtual_list import Column, VirtualList
from .base import Page
from ... import system
from ...constants import MIN_FREE_BYTES


class PlaylistPage(Page):
    title = "Playlist Downloader"
    subtitle = "Fetch a playlist, choose the videos, then download them as MP4 or MP3."

    def __init__(self, parent, ctx):
        super().__init__(parent, ctx)
        self.grid_rowconfigure(4, weight=3)
        self.grid_rowconfigure(6, weight=2)
        self.info: Optional[PlaylistInfo] = None
        self.checked: Set[int] = set()
        self._status: Dict[str, object] = {}
        self._fetch_token = 0
        self.header()

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        self.url = widgets.entry(top, placeholder="Paste a YouTube playlist link here")
        self.url.grid(row=0, column=0, sticky="ew")
        self.url.bind("<Return>", lambda e: self.start_fetch())
        self.fetch_btn = widgets.primary_button(top, "Fetch Playlist", self.start_fetch, width=150, height=42)
        self.fetch_btn.grid(row=0, column=1, padx=(10, 0))
        self.banner = widgets.Banner(self)
        self.banner.grid(row=2, column=0, sticky="ew", pady=(6, 6))

        info = widgets.card(self)
        info.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        info.grid_columnconfigure(1, weight=1)
        self.thumb = widgets.Thumbnail(info, (128, 72))
        self.thumb.grid(row=0, column=0, rowspan=3, padx=14, pady=12)
        self.p_title = widgets.label(info, "No playlist loaded", 15, "bold", anchor="w")
        self.p_title.grid(row=0, column=1, sticky="sw", pady=(12, 0))
        self.p_meta = widgets.muted(info, "Fetch a playlist to see its videos.", 12, anchor="w")
        self.p_meta.grid(row=1, column=1, sticky="nw")
        opts = ctk.CTkFrame(info, fg_color="transparent")
        opts.grid(row=2, column=1, sticky="ew", pady=(4, 12), padx=(0, 14))
        opts.grid_columnconfigure(1, weight=1)
        self.formats = FormatPicker(opts, ctx)
        self.formats.grid(row=0, column=0, sticky="w")
        self.folder = FolderPicker(opts, ctx)
        self.folder.grid(row=0, column=1, sticky="ew", padx=(14, 0))

        self.rows: List[dict] = []
        self.list = VirtualList(self, [Column("check", 44, "check"), Column("index", 46, muted=True, anchor="e"),
                                       Column("title"), Column("duration", 80, muted=True, anchor="e"),
                                       Column("status", 170, "status")],
                                self._row, lambda: len(self.entries), row_height=50,
                                on_toggle=self._toggle, on_select=lambda i: None, on_double=self._toggle,
                                empty_text="Videos in the playlist will be listed here.")
        self.list.grid(row=4, column=0, sticky="nsew")

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=5, column=0, sticky="ew", pady=10)
        widgets.secondary_button(bar, "Select all", self._all, width=90).pack(side="left")
        widgets.secondary_button(bar, "Select none", self._none, width=100).pack(side="left", padx=8)
        self.count = widgets.muted(bar, "", 12)
        self.count.pack(side="left", padx=8)
        self.dl_btn = widgets.primary_button(bar, "Download selected", self._download, width=170, height=40)
        self.dl_btn.pack(side="right")
        self.dl_btn.configure(state="disabled")

        self.queue = QueueView(self, ctx, source="playlist", empty_text="Videos you download from a playlist appear here with live progress.")
        self.queue.grid(row=6, column=0, sticky="nsew")

    @property
    def entries(self) -> List[EntryInfo]:
        return self.info.entries if self.info else []

    # -- fetching -----------------------------------------------------------

    def start_fetch(self, url: Optional[str] = None) -> None:
        if url is not None:
            self.url.delete(0, "end")
            self.url.insert(0, url)
        check = urls.check_playlist_url(self.url.get())
        if not check.ok:
            self.banner.show(check.message, "error")
            return
        self._fetch_token += 1
        token = self._fetch_token
        self.fetch_btn.configure(state="disabled", text="Fetching…")
        self.banner.show("Reading the playlist… large playlists can take a little while.", "info")

        def done(result, error):
            if token != self._fetch_token:
                return
            self.fetch_btn.configure(state="normal", text="Fetch Playlist")
            if error is not None:
                msg = error.friendly.message if isinstance(error, FetchError) else "Something went wrong while reading that playlist."
                self.banner.show(msg, "error")
                return
            self._load(result)

        self.ctx.run_async(lambda: fetch_playlist(check.url), done)

    def _load(self, info: PlaylistInfo) -> None:
        self.info = info
        self.checked = set(range(len(info.entries)))
        self.p_title.configure(text=info.title or "Playlist")
        total = sum(e.duration or 0 for e in info.entries)
        meta = f"{len(info.entries)} videos"
        if total:
            meta += f"  ·  {format_duration(total)} total"
        if info.uploader:
            meta += f"  ·  {info.uploader}"
        self.p_meta.configure(text=meta)
        self.thumb.clear()
        token = self._fetch_token
        self.ctx.run_async(lambda: fetch_thumbnail(info.thumbnail_url),
                           lambda data, err: self.thumb.set_bytes(data) if token == self._fetch_token and not err else None)
        note = f"{info.unavailable} private or deleted videos were skipped." if info.unavailable else ""
        self.banner.show(("Playlist ready. " + note).strip(), "success" if not note else "warn")
        self.list.reset_scroll()
        self._update_status_map()
        self.list.refresh()
        self._update_count()

    # -- list ---------------------------------------------------------------

    def _update_status_map(self) -> None:
        self._status = {i.video_id: i for i in self.ctx.manager.snapshot() if i.source == "playlist"}

    def _row(self, index: int) -> dict:
        e = self.entries[index]
        item = self._status.get(e.video_id)
        row = {"check": index in self.checked, "index": str(index + 1), "title": e.title,
               "duration": format_duration(e.duration) if e.duration else "—", "status": "", "progress": None}
        if item:
            row.update({k: v for k, v in item_row(item).items() if k in ("status", "status_color", "progress")})
        return row

    def _toggle(self, index: int) -> None:
        self.checked.symmetric_difference_update({index})
        self.list.refresh()
        self._update_count()

    def _all(self) -> None:
        self.checked = set(range(len(self.entries)))
        self.list.refresh()
        self._update_count()

    def _none(self) -> None:
        self.checked.clear()
        self.list.refresh()
        self._update_count()

    def _update_count(self) -> None:
        n = len(self.checked)
        self.count.configure(text=f"{n} of {len(self.entries)} selected" if self.entries else "")
        self.dl_btn.configure(state="normal" if n else "disabled")

    # -- download -----------------------------------------------------------

    def _download(self) -> None:
        folder = self.folder.path or self.ctx.settings.effective_download_dir()
        ok, msg = system.prepare_folder(folder, MIN_FREE_BYTES)
        if not ok:
            self.banner.show(msg, "error")
            return
        self.folder._persist()
        preset = self.formats.preset_id
        batch = self.info.url if self.info else ""
        items = [new_item(self.entries[i], preset, folder, "playlist", batch) for i in sorted(self.checked)]
        accepted, dupes = self.ctx.manager.enqueue(items)
        text = f"Added {len(accepted)} video(s) to the queue as {self.formats.preset_label}."
        if dupes:
            text += f" {dupes} already in the queue."
        self.banner.show(text, "success" if accepted else "warn")
        self._update_status_map()
        self.list.refresh()

    # -- hooks --------------------------------------------------------------

    def on_engine_event(self, kind, payload) -> None:
        self.queue.on_engine_event(kind, payload)
        if self.info:
            self._update_status_map()
            self.list.refresh()

    def on_show(self) -> None:
        self.queue.reload()
        self.folder.refresh()

    def on_settings_changed(self) -> None:
        self.folder.refresh()
