from __future__ import annotations

import customtkinter as ctk

from ...engine import summarize
from ...utils import format_bytes, format_eta, format_speed, format_when
from .. import theme, widgets
from ..virtual_list import Column, VirtualList
from .base import Page


class DashboardPage(Page):
    title = "Dashboard"
    subtitle = "Download whole playlists in the quality you choose."

    def __init__(self, parent, ctx):
        super().__init__(parent, ctx)
        self.grid_rowconfigure(5, weight=1)
        self.header()

        hero = widgets.card(self)
        hero.grid(row=1, column=0, sticky="ew")
        hero.grid_columnconfigure(1, weight=1)
        logo = widgets.logo_image(64)
        ctk.CTkLabel(hero, text="" if logo else "K", image=logo, width=64).grid(row=0, column=0, rowspan=2, padx=(20, 14), pady=18)
        widgets.label(hero, "K Downloader", 20, "bold").grid(row=0, column=1, sticky="sw", pady=(18, 0))
        from ...constants import __version__
        widgets.muted(hero, f"Version {__version__}  ·  by KAUSHAN", 12).grid(row=1, column=1, sticky="nw", pady=(0, 18))
        row = ctk.CTkFrame(hero, fg_color="transparent")
        row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 18))
        row.grid_columnconfigure(0, weight=1)
        self.url = widgets.entry(row, placeholder="Paste a YouTube playlist link here")
        self.url.grid(row=0, column=0, sticky="ew")
        self.url.bind("<Return>", lambda e: self._fetch())
        widgets.primary_button(row, "Fetch Playlist", self._fetch, width=150, height=42).grid(row=0, column=1, padx=(10, 0))

        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.grid(row=2, column=0, sticky="ew", pady=14)
        for c in range(4):
            stats.grid_columnconfigure(c, weight=1, uniform="stat")
        self.s_done = widgets.StatCard(stats, "Completed", "0", "all time")
        self.s_fail = widgets.StatCard(stats, "Failed", "0", "all time")
        self.s_queue = widgets.StatCard(stats, "In queue", "0", "waiting or downloading")
        self.s_size = widgets.StatCard(stats, "Downloaded", "0 B", "all time")
        for c, card in enumerate((self.s_done, self.s_fail, self.s_queue, self.s_size)):
            card.grid(row=0, column=c, sticky="ew", padx=(0 if c == 0 else 6, 0 if c == 3 else 6))

        prog = widgets.card(self)
        prog.grid(row=3, column=0, sticky="ew")
        prog.grid_columnconfigure(0, weight=1)
        widgets.label(prog, "Progress overview", 13, "bold").grid(row=0, column=0, sticky="w", padx=18, pady=(14, 6))
        self.bar = widgets.progress_bar(prog, height=10)
        self.bar.set(0)
        self.bar.grid(row=1, column=0, sticky="ew", padx=18)
        self.prog_text = widgets.muted(prog, "Nothing is downloading.", 12)
        self.prog_text.grid(row=2, column=0, sticky="w", padx=18, pady=(6, 14))

        widgets.label(self, "Recent downloads", 13, "bold").grid(row=4, column=0, sticky="w", pady=(14, 6))
        self.recent: list = []
        self.list = VirtualList(self, [Column("title"), Column("when", 150, muted=True, anchor="e"), Column("status", 120, "status")],
                                lambda i: self.recent[i], lambda: len(self.recent), row_height=44,
                                on_double=lambda i: self.ctx.navigate("history"), empty_text="Your finished downloads will appear here.")
        self.list.grid(row=5, column=0, sticky="nsew")
        self.list.configure(height=170)

    def _fetch(self) -> None:
        url = self.url.get().strip()
        self.ctx.navigate("playlist")
        self.ctx.pages["playlist"].start_fetch(url)

    def on_show(self) -> None:
        self.refresh()

    def on_engine_event(self, kind, payload) -> None:
        self.refresh()

    def refresh(self) -> None:
        st = self.ctx.history.stats()
        s = summarize(self.ctx.manager.snapshot())
        self.s_done.set(str(st["completed"]))
        self.s_fail.set(str(st["failed"]))
        self.s_queue.set(str(s["queued"] + s["active"]))
        self.s_size.set(format_bytes(st["bytes"]))
        self.bar.set(s["progress"] if s["total"] else 0)
        if s["queued"] + s["active"]:
            bits = [f"{s['finished']} of {s['total']} finished"]
            if s["speed"]:
                bits.append(format_speed(s["speed"]))
            if s["eta"] is not None:
                bits.append(f"about {format_eta(s['eta'])} left")
            self.prog_text.configure(text="  ·  ".join(bits))
        elif s["total"]:
            self.prog_text.configure(text=f"Finished: {s['completed'] + s['skipped']} saved, {s['failed']} failed.")
        else:
            self.prog_text.configure(text="Nothing is downloading.")
        colors = {"Completed": theme.SUCCESS, "Already saved": theme.SUCCESS, "Failed": theme.DANGER, "Cancelled": theme.WARNING}
        self.recent = [{"title": r.get("title", ""), "when": format_when(r.get("finished_at")),
                        "status": r.get("status", ""), "status_color": colors.get(r.get("status"), theme.MUTED)}
                       for r in self.ctx.history.all()[:8]]
        self.list.refresh()
