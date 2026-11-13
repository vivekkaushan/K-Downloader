from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from ... import system, urls
from ...constants import MIN_FREE_BYTES
from ...engine import EntryInfo, FetchError, fetch_thumbnail, fetch_video, new_item
from ...utils import format_duration
from .. import widgets
from ..pickers import FolderPicker, FormatPicker
from ..queue_view import QueueView
from .base import Page


class SingleVideoPage(Page):
    title = "Single Video Downloader"
    subtitle = "Download one video, or just its audio as MP3."

    def __init__(self, parent, ctx):
        super().__init__(parent, ctx)
        self.grid_rowconfigure(5, weight=1)
        self.entry_info: Optional[EntryInfo] = None
        self._token = 0
        self.header()
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        self.url = widgets.entry(top, placeholder="Paste a YouTube video link here")
        self.url.grid(row=0, column=0, sticky="ew")
        self.url.bind("<Return>", lambda e: self._check())
        self.check_btn = widgets.primary_button(top, "Check Video", self._check, width=150, height=42)
        self.check_btn.grid(row=0, column=1, padx=(10, 0))
        self.banner = widgets.Banner(self)
        self.banner.grid(row=2, column=0, sticky="ew", pady=(6, 6))

        card = widgets.card(self)
        card.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        card.grid_columnconfigure(1, weight=1)
        self.thumb = widgets.Thumbnail(card, (160, 90))
        self.thumb.grid(row=0, column=0, rowspan=3, padx=14, pady=14)
        self.v_title = widgets.label(card, "No video loaded", 15, "bold", anchor="w", wraplength=520, justify="left")
        self.v_title.grid(row=0, column=1, sticky="sw", pady=(14, 0))
        self.v_meta = widgets.muted(card, "Paste a link and press Check Video.", 12, anchor="w")
        self.v_meta.grid(row=1, column=1, sticky="nw")
        opts = ctk.CTkFrame(card, fg_color="transparent")
        opts.grid(row=2, column=1, sticky="ew", padx=(0, 14), pady=(6, 14))
        opts.grid_columnconfigure(1, weight=1)
        self.formats = FormatPicker(opts, ctx)
        self.formats.grid(row=0, column=0, sticky="w")
        self.folder = FolderPicker(opts, ctx)
        self.folder.grid(row=0, column=1, sticky="ew", padx=(14, 0))

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        self.dl_btn = widgets.primary_button(bar, "Download", self._download, width=150, height=40)
        self.dl_btn.pack(side="left")
        self.dl_btn.configure(state="disabled")

        self.queue = QueueView(self, ctx, source="single", empty_text="Single videos you download appear here.")
        self.queue.grid(row=5, column=0, sticky="nsew")

    def _check(self) -> None:
        check = urls.check_video_url(self.url.get())
        if not check.ok:
            self.banner.show(check.message, "error")
            return
        self._token += 1
        token = self._token
        self.check_btn.configure(state="disabled", text="Checking…")
        self.banner.show("Looking up the video…", "info")

        def done(result, error):
            if token != self._token:
                return
            self.check_btn.configure(state="normal", text="Check Video")
            if error is not None:
                self.entry_info = None
                self.dl_btn.configure(state="disabled")
                self.banner.show(error.friendly.message if isinstance(error, FetchError) else "Couldn't read that video.", "error")
                return
            self.entry_info = result
            self.v_title.configure(text=result.title)
            bits = [format_duration(result.duration)] if result.duration else []
            if result.uploader:
                bits.append(result.uploader)
            self.v_meta.configure(text="  ·  ".join(bits) or "Ready to download.")
            self.banner.show("Video found.", "success")
            self.dl_btn.configure(state="normal")
            self.thumb.clear()
            self.ctx.run_async(lambda: fetch_thumbnail(result.thumbnail_url),
                               lambda d, e: self.thumb.set_bytes(d) if token == self._token and not e else None)

        self.ctx.run_async(lambda: fetch_video(check.url), done)

    def _download(self) -> None:
        if not self.entry_info:
            return
        folder = self.folder.path or self.ctx.settings.effective_download_dir()
        ok, msg = system.prepare_folder(folder, MIN_FREE_BYTES)
        if not ok:
            self.banner.show(msg, "error")
            return
        self.folder._persist()
        item = new_item(self.entry_info, self.formats.preset_id, folder, "single")
        accepted, dupes = self.ctx.manager.enqueue([item])
        self.banner.show("Added to the queue." if accepted else "That video is already in the queue.", "success" if accepted else "warn")

    def on_engine_event(self, kind, payload) -> None:
        self.queue.on_engine_event(kind, payload)

    def on_show(self) -> None:
        self.queue.reload()
        self.folder.refresh()

    def on_settings_changed(self) -> None:
        self.folder.refresh()
