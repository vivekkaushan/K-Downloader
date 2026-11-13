from __future__ import annotations

import customtkinter as ctk

from ... import formats, system, updates
from ...constants import __version__
from ...config import Settings
from .. import dialogs, theme, widgets
from ..pickers import FolderPicker
from .base import Page

_THEMES = {"Dark": "dark", "Light": "light", "System": "system"}


class SettingsPage(Page):
    title = "Settings"
    subtitle = "Saved automatically on this computer."

    def __init__(self, parent, ctx):
        super().__init__(parent, ctx)
        self.header()
        body = widgets.card(self)
        body.grid(row=1, column=0, sticky="ew")
        body.grid_columnconfigure(1, weight=1)
        self._r = 0

        self.theme_seg = widgets.segmented(body, list(_THEMES), command=self._theme, width=240)
        self._row(body, "Theme", self.theme_seg)
        self.folder = FolderPicker(body, ctx)
        self._row(body, "Download folder", self.folder, sticky="ew")
        self.kind_seg = widgets.segmented(body, ["Video", "Audio"], command=self._kind, width=150)
        self._row(body, "Default format", self.kind_seg)
        self.vq = widgets.option_menu(body, ["—"], command=self._vq, width=210)
        self._row(body, "Default video quality", self.vq)
        self.aq = widgets.option_menu(body, ["—"], command=self._aq, width=210)
        self._row(body, "Default audio quality", self.aq)
        self.hist = ctk.CTkSwitch(body, text="Keep a download history", command=self._hist, progress_color=theme.PRIMARY)
        self._row(body, "History", self.hist)
        self.max_menu = widgets.option_menu(body, ["100", "250", "500", "1000", "2500"], command=self._max, width=110)
        self._row(body, "History limit", self.max_menu)

        tools = widgets.card(self)
        tools.grid(row=2, column=0, sticky="ew", pady=12)
        tools.grid_columnconfigure(0, weight=1)
        widgets.label(tools, f"K Downloader {__version__}", 13, "bold").grid(row=0, column=0, sticky="w", padx=18, pady=(14, 0))
        self.ffmpeg_text = widgets.muted(tools, "", 12, anchor="w", justify="left", wraplength=560)
        self.ffmpeg_text.grid(row=1, column=0, sticky="w", padx=18)
        self.update_text = widgets.muted(tools, "Updates are only checked when you ask.", 12, anchor="w", wraplength=560, justify="left")
        self.update_text.grid(row=2, column=0, sticky="w", padx=18, pady=(2, 12))
        btns = ctk.CTkFrame(tools, fg_color="transparent")
        btns.grid(row=0, column=1, rowspan=3, padx=18)
        self.update_btn = widgets.secondary_button(btns, "Check for updates", self._check_updates, width=150)
        self.update_btn.pack(pady=(0, 8))
        widgets.secondary_button(btns, "Restore defaults", self._restore, width=150).pack()
        self.on_settings_changed()

    def _row(self, body, name, widget, sticky="w") -> None:
        widgets.label(body, name, 13).grid(row=self._r, column=0, sticky="w", padx=(18, 24), pady=10)
        widget.grid(row=self._r, column=1, sticky=sticky, padx=(0, 18), pady=10)
        self._r += 1

    def _save(self) -> None:
        self.ctx.save_settings()

    def _theme(self, v) -> None:
        self.ctx.settings.theme = _THEMES[v]
        self._save()
        theme.apply_mode(self.ctx.settings.theme)
        self.ctx.theme_changed()

    def _kind(self, v) -> None:
        self.ctx.settings.default_kind = formats.AUDIO if v == "Audio" else formats.VIDEO
        self._save()

    def _vq(self, label) -> None:
        self.ctx.settings.default_video_quality = self._vmap[label]
        self._save()

    def _aq(self, label) -> None:
        self.ctx.settings.default_audio_quality = self._amap[label]
        self._save()

    def _hist(self) -> None:
        self.ctx.settings.keep_history = bool(self.hist.get())
        self._save()

    def _max(self, v) -> None:
        self.ctx.settings.max_history = int(v)
        self.ctx.history.set_max(int(v))
        self._save()

    def on_settings_changed(self) -> None:
        s = self.ctx.settings
        self.theme_seg.set(next(k for k, v in _THEMES.items() if v == s.theme))
        self.folder.refresh()
        self.kind_seg.set("Audio" if s.default_kind == formats.AUDIO else "Video")
        vp, ap = self.ctx.presets(formats.VIDEO), self.ctx.presets(formats.AUDIO)
        self._vmap, self._amap = {p.label: p.id for p in vp}, {p.label: p.id for p in ap}
        self.vq.configure(values=list(self._vmap))
        self.vq.set(next((p.label for p in vp if p.id == s.default_video_quality), vp[0].label))
        self.aq.configure(values=list(self._amap))
        self.aq.set(next((p.label for p in ap if p.id == s.default_audio_quality), ap[0].label))
        self.hist.select() if s.keep_history else self.hist.deselect()
        self.max_menu.set(str(s.max_history) if str(s.max_history) in ("100", "250", "500", "1000", "2500") else "500")
        if self.ctx.ffmpeg_ok:
            self.ffmpeg_text.configure(text="FFmpeg: ready. MP3 conversion and best-quality merging are available.")
        else:
            self.ffmpeg_text.configure(text="FFmpeg: not found. MP3 conversion and some quality options are unavailable; "
                                            "ready-made MP4 and audio formats still work.")

    def _restore(self) -> None:
        if not dialogs.ask(self.winfo_toplevel(), "Restore defaults?", "Settings return to their original values. Your history and downloads are kept.", ok="Restore"):
            return
        fresh = self.ctx.settings_store.reset()
        for key, value in vars(fresh).items():
            setattr(self.ctx.settings, key, value)
        theme.apply_mode(self.ctx.settings.theme)
        self.ctx.history.set_max(self.ctx.settings.max_history)
        self.ctx.theme_changed()
        self.ctx.settings_changed()

    def _check_updates(self) -> None:
        self.update_btn.configure(state="disabled", text="Checking…")
        self.update_text.configure(text="Contacting GitHub…")

        def done(res, err):
            self.update_btn.configure(state="normal", text="Check for updates")
            if err or res is None:
                self.update_text.configure(text="Couldn't check for updates.")
            elif res.status == "available":
                self.update_text.configure(text=f"Version {res.latest} is available.")
                if dialogs.ask(self.winfo_toplevel(), "Update available", f"Version {res.latest} is available. Open the download page?", ok="Open page"):
                    widgets.open_url(res.url)
            elif res.status == "up_to_date":
                self.update_text.configure(text="You have the latest version.")
            else:
                self.update_text.configure(text=res.message or "No update information available.")

        self.ctx.run_async(updates.check_for_updates, done)

    def on_show(self) -> None:
        self.on_settings_changed()
