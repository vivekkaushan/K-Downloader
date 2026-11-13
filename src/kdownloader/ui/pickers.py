"""Format and folder pickers shared by several pages."""

from __future__ import annotations

import tkinter.filedialog as filedialog
from pathlib import Path
from typing import Dict, Optional

import customtkinter as ctk

from .. import formats, system
from . import dialogs, theme, widgets
from .context import AppContext


class FormatPicker(ctk.CTkFrame):
    """Video/Audio switch plus a quality menu (conversion options only with FFmpeg)."""

    def __init__(self, parent, ctx: AppContext):
        super().__init__(parent, fg_color="transparent")
        self.ctx = ctx
        self._labels: Dict[str, str] = {}
        self.kind_button = widgets.segmented(self, ["Video", "Audio"], command=self._kind_changed, width=150)
        self.kind_button.pack(side="left")
        self.menu = widgets.option_menu(self, ["—"], width=210)
        self.menu.pack(side="left", padx=(10, 0))
        self.apply_defaults()

    def apply_defaults(self) -> None:
        s = self.ctx.settings
        kind = s.default_kind
        self.kind_button.set("Audio" if kind == formats.AUDIO else "Video")
        self._populate(kind, s.default_audio_quality if kind == formats.AUDIO else s.default_video_quality)

    @property
    def kind(self) -> str:
        return formats.AUDIO if self.kind_button.get() == "Audio" else formats.VIDEO

    @property
    def preset_id(self) -> str:
        return self._labels.get(self.menu.get()) or formats.DEFAULT_VIDEO_PRESET

    @property
    def preset_label(self) -> str:
        return formats.get_preset(self.preset_id).label

    def _kind_changed(self, value: str) -> None:
        kind = formats.AUDIO if value == "Audio" else formats.VIDEO
        s = self.ctx.settings
        self._populate(kind, s.default_audio_quality if kind == formats.AUDIO else s.default_video_quality)

    def _populate(self, kind: str, preferred: Optional[str]) -> None:
        presets = self.ctx.presets(kind)
        self._labels = {p.label: p.id for p in presets}
        labels = list(self._labels)
        chosen = next((p.label for p in presets if p.id == preferred), labels[0] if labels else "—")
        self.menu.configure(values=labels or ["—"])
        self.menu.set(chosen)


class FolderPicker(ctk.CTkFrame):
    """Shows and edits the download folder; remembers the choice."""

    def __init__(self, parent, ctx: AppContext, compact: bool = False):
        super().__init__(parent, fg_color="transparent")
        self.ctx = ctx
        self.var = ctk.StringVar(value=ctx.settings.effective_download_dir())
        self.grid_columnconfigure(0, weight=1)
        self.entry = widgets.entry(self, textvariable=self.var, height=34)
        self.entry.grid(row=0, column=0, sticky="ew")
        self.entry.bind("<Return>", lambda e: self._persist())
        self.entry.bind("<FocusOut>", lambda e: self._persist())
        widgets.secondary_button(self, "Browse…", self._browse, width=90).grid(row=0, column=1, padx=(8, 0))
        widgets.secondary_button(self, "Open folder", self.open_folder, width=100).grid(row=0, column=2, padx=(8, 0))

    @property
    def path(self) -> str:
        return self.var.get().strip()

    def refresh(self) -> None:
        if self.focus_get() is not self.entry._entry:
            self.var.set(self.ctx.settings.effective_download_dir())

    def _persist(self) -> None:
        path = self.path
        if path and path != self.ctx.settings.download_dir:
            self.ctx.settings.download_dir = path
            self.ctx.save_settings()
            self.ctx.settings_changed()

    def _browse(self) -> None:
        start = system.nearest_existing_parent(self.path or Path.home())
        folder = filedialog.askdirectory(parent=self.winfo_toplevel(), initialdir=str(start),
                                         title="Choose the download folder")
        if folder:
            self.var.set(folder)
            self._persist()

    def open_folder(self) -> None:
        target = Path(self.path).expanduser()
        if target.is_dir():
            system.open_path(target)
        else:
            dialogs.notify(self.winfo_toplevel(), "Folder not found",
                           "That folder doesn't exist yet. It will be created when you start a download.")
