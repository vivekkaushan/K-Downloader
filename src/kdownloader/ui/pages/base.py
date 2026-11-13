"""Common page behaviour."""

from __future__ import annotations

import customtkinter as ctk

from ..context import AppContext
from .. import widgets


class Page(ctk.CTkFrame):
    title = ""
    subtitle = ""

    def __init__(self, parent, ctx: AppContext):
        super().__init__(parent, fg_color="transparent")
        self.ctx = ctx
        self.grid_columnconfigure(0, weight=1)

    def header(self, row: int = 0) -> None:
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.grid(row=row, column=0, sticky="ew", pady=(0, 14))
        widgets.label(box, self.title, 24, "bold").pack(anchor="w")
        if self.subtitle:
            widgets.muted(box, self.subtitle, 12).pack(anchor="w")

    # hooks -----------------------------------------------------------------
    def on_show(self) -> None: ...
    def on_engine_event(self, kind: str, payload) -> None: ...
    def on_settings_changed(self) -> None: ...
