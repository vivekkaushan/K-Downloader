from __future__ import annotations

import customtkinter as ctk

from ... import formats, system
from ...utils import format_bytes, format_when
from .. import dialogs, theme, widgets
from ..virtual_list import Column, VirtualList
from .base import Page

_COLORS = {"Completed": theme.SUCCESS, "Already saved": theme.SUCCESS, "Failed": theme.DANGER, "Cancelled": theme.WARNING}


class HistoryPage(Page):
    title = "Download History"
    subtitle = "Everything you've downloaded, stored only on this computer."

    def __init__(self, parent, ctx):
        super().__init__(parent, ctx)
        self.grid_rowconfigure(2, weight=1)
        self.header()
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        self.open_btn = widgets.secondary_button(bar, "Show in folder", self._open, width=120)
        self.again_btn = widgets.secondary_button(bar, "Download again", self._again, width=130)
        self.remove_btn = widgets.secondary_button(bar, "Remove", self._remove, width=90)
        self.clear_btn = widgets.danger_button(bar, "Clear history", self._clear, width=110)
        for b in (self.open_btn, self.again_btn, self.remove_btn):
            b.pack(side="left", padx=(0, 8))
        self.clear_btn.pack(side="right")
        self.records: list = []
        self.list = VirtualList(self, [Column("title"), Column("detail", 150, muted=True, anchor="e"), Column("when", 140, muted=True, anchor="e"),
                                       Column("status", 120, "status")],
                                self._row, lambda: len(self.records), row_height=52,
                                on_select=lambda i: self._buttons(), on_double=lambda i: self._open(),
                                empty_text="No downloads yet. Finished downloads will be listed here.")
        self.list.grid(row=2, column=0, sticky="nsew")

    def _row(self, i: int) -> dict:
        r = self.records[i]
        preset = formats.get_preset(r.get("preset", "")).label if r.get("preset") else ""
        detail = " · ".join(x for x in (preset, format_bytes(r["size"]) if r.get("size") else "") if x)
        row = {"title": r.get("title", ""), "detail": detail, "when": format_when(r.get("finished_at")),
               "status": r.get("status", ""), "status_color": _COLORS.get(r.get("status"), theme.MUTED)}
        if r.get("status") == "Failed" and r.get("error"):
            row["title_sub"], row["title_sub_color"] = r["error"], theme.DANGER
        return row

    def _sel(self):
        i = self.list.selected
        return self.records[i] if i is not None and i < len(self.records) else None

    def _buttons(self) -> None:
        sel = self._sel()
        self.open_btn.configure(state="normal" if sel and sel.get("dest_dir") else "disabled")
        self.again_btn.configure(state="normal" if sel and sel.get("url") else "disabled")
        self.remove_btn.configure(state="normal" if sel else "disabled")
        self.clear_btn.configure(state="normal" if self.records else "disabled")

    def reload(self) -> None:
        sel = self._sel()
        self.records = self.ctx.history.all()
        self.list.selected = next((n for n, r in enumerate(self.records) if sel and r.get("id") == sel.get("id")), None)
        self.list.refresh()
        self._buttons()

    def on_show(self) -> None:
        self.reload()

    def on_engine_event(self, kind, payload) -> None:
        if kind == "finished":
            self.reload()

    def _open(self) -> None:
        r = self._sel()
        if not r:
            return
        target = r.get("filepath") if r.get("filepath") and __import__("os").path.exists(r["filepath"]) else r.get("dest_dir")
        if not target or not system.open_path(target):
            dialogs.notify(self.winfo_toplevel(), "Can't open it", "The file or folder no longer exists.")

    def _again(self) -> None:
        from ...engine import EntryInfo, new_item
        r = self._sel()
        if not r:
            return
        entry = EntryInfo(video_id=r.get("video_id", ""), title=r.get("title", ""), url=r["url"])
        item = new_item(entry, r.get("preset") or self.ctx.settings.default_video_quality,
                        r.get("dest_dir") or self.ctx.settings.effective_download_dir(), r.get("source", "single"))
        self.ctx.manager.enqueue([item])
        self.ctx.navigate("playlist" if item.source == "playlist" else "single")

    def _remove(self) -> None:
        r = self._sel()
        if r:
            self.ctx.history.remove(r["id"])
            self.reload()

    def _clear(self) -> None:
        if dialogs.ask(self.winfo_toplevel(), "Clear history?", "This removes the list only. Your downloaded files are not deleted.",
                       ok="Clear", danger=True):
            self.ctx.history.clear()
            self.reload()
