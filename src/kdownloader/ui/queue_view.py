"""Queue list with controls (stop, cancel, retry, clear) bound to the download manager."""

from __future__ import annotations

from typing import List, Optional

import customtkinter as ctk

from .. import formats
from ..engine import DownloadItem, Status, summarize
from ..utils import format_eta, format_speed
from . import theme, widgets
from .context import AppContext
from .virtual_list import Column, VirtualList

_STATUS_COLORS = {
    Status.QUEUED: theme.MUTED, Status.DOWNLOADING: theme.ACCENT, Status.PROCESSING: theme.ACCENT,
    Status.COMPLETED: theme.SUCCESS, Status.SKIPPED: theme.SUCCESS, Status.FAILED: theme.DANGER,
    Status.CANCELLED: theme.WARNING,
}
_RANK = {Status.DOWNLOADING: 0, Status.PROCESSING: 0, Status.QUEUED: 1}


def status_text(item: DownloadItem) -> str:
    if item.status == Status.DOWNLOADING:
        if item.note:
            return item.note
        bits = [f"{int(item.progress * 100)}%"]
        if item.speed:
            bits.append(format_speed(item.speed))
        if item.eta is not None:
            bits.append(f"{format_eta(item.eta)} left")
        return "  ·  ".join(bits)
    if item.status == Status.PROCESSING:
        return "Processing…"
    return item.status


def item_row(item: DownloadItem, sub_text: Optional[str] = None) -> dict:
    row = {"title": item.title, "status": status_text(item), "status_color": _STATUS_COLORS.get(item.status, theme.MUTED),
           "progress": item.progress if item.status in Status.ACTIVE else None}
    if item.status == Status.FAILED and item.error:
        row["title_sub"], row["title_sub_color"] = item.error, theme.DANGER
    elif sub_text:
        row["title_sub"] = sub_text
    return row


class QueueView(ctk.CTkFrame):
    def __init__(self, parent, ctx: AppContext, source: Optional[str] = None, empty_text: str = "No downloads yet."):
        super().__init__(parent, fg_color="transparent")
        self.ctx, self.source = ctx, source
        self.items: List[DownloadItem] = []
        self._pending = False
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        self.stop_btn = widgets.danger_button(bar, "Stop all", self._stop_all, width=84)
        self.cancel_btn = widgets.secondary_button(bar, "Cancel selected", self._cancel_selected, width=120)
        self.retry_btn = widgets.secondary_button(bar, "Retry failed", self._retry, width=100)
        self.clear_btn = widgets.secondary_button(bar, "Clear finished", self._clear, width=110)
        for b in (self.stop_btn, self.cancel_btn, self.retry_btn, self.clear_btn):
            b.pack(side="left", padx=(0, 8))
        self.summary = widgets.muted(bar, "", 11)
        self.summary.pack(side="right")

        self.list = VirtualList(self, [Column("title"), Column("status", 215, "status")], self._row,
                                lambda: len(self.items), row_height=52, on_select=lambda i: self._buttons(),
                                empty_text=empty_text)
        self.list.grid(row=1, column=0, sticky="nsew")
        self.reload()

    # -- data -------------------------------------------------------------

    def schedule_reload(self) -> None:
        if not self._pending:
            self._pending = True
            self.after(150, self.reload)

    def on_engine_event(self, kind: str, payload) -> None:
        self.schedule_reload()

    def reload(self) -> None:
        self._pending = False
        items = [i for i in self.ctx.manager.snapshot() if self.source is None or i.source == self.source]
        live = sorted((i for i in items if not i.is_terminal), key=lambda i: (_RANK.get(i.status, 2), i.queued_at))
        done = sorted((i for i in items if i.is_terminal), key=lambda i: i.finished_at, reverse=True)
        selected_id = self.items[self.list.selected].id if self.list.selected is not None and self.list.selected < len(self.items) else None
        self.items = live + done
        self.list.selected = next((n for n, i in enumerate(self.items) if i.id == selected_id), None)
        self.list.refresh()
        s = summarize(self.items)
        self.summary.configure(text=f"{s['completed'] + s['skipped']} done · {s['failed']} failed · {s['queued'] + s['active']} in queue" if self.items else "")
        self._buttons()

    def _row(self, index: int) -> dict:
        item = self.items[index]
        sub = "Playlist" if item.source == "playlist" else "Single video"
        return item_row(item, f"{sub} · {formats.get_preset(item.preset_id).label}")

    def _selected(self) -> Optional[DownloadItem]:
        i = self.list.selected
        return self.items[i] if i is not None and i < len(self.items) else None

    def _buttons(self) -> None:
        busy = any(not i.is_terminal for i in self.items)
        sel = self._selected()
        self.stop_btn.configure(state="normal" if busy else "disabled")
        self.cancel_btn.configure(state="normal" if sel and not sel.is_terminal else "disabled")
        self.retry_btn.configure(state="normal" if any(i.status in (Status.FAILED, Status.CANCELLED) for i in self.items) else "disabled")
        self.clear_btn.configure(state="normal" if any(i.is_terminal for i in self.items) else "disabled")

    # -- actions ----------------------------------------------------------

    def _stop_all(self) -> None:
        for item in self.items:
            if not item.is_terminal:
                self.ctx.manager.cancel(item.id)

    def _cancel_selected(self) -> None:
        sel = self._selected()
        if sel:
            self.ctx.manager.cancel(sel.id)

    def _retry(self) -> None:
        self.ctx.manager.retry([i.id for i in self.items if i.status in (Status.FAILED, Status.CANCELLED)])

    def _clear(self) -> None:
        self.ctx.manager.remove([i.id for i in self.items if i.is_terminal])
