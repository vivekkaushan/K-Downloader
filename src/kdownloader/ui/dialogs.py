"""Small modal dialogs in the app's style."""

from __future__ import annotations

from typing import List, Optional, Tuple

import customtkinter as ctk

from . import theme, widgets


class _Dialog(ctk.CTkToplevel):
    def __init__(self, parent, title: str, message: str, buttons: List[Tuple[str, object, str]], width: int = 440):
        super().__init__(parent)
        self.result = None
        self.title(title)
        self.configure(fg_color=theme.BG)
        self.resizable(False, False)
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        box = widgets.card(self)
        box.pack(fill="both", expand=True, padx=14, pady=14)
        widgets.label(box, title, 17, "bold").pack(anchor="w", padx=20, pady=(18, 6))
        widgets.muted(box, message, 13, wraplength=width - 80, justify="left").pack(anchor="w", padx=20, pady=(0, 16))
        row = ctk.CTkFrame(box, fg_color="transparent")
        row.pack(anchor="e", padx=20, pady=(0, 18))
        for text, value, style in buttons:
            make = {"primary": widgets.primary_button, "danger": widgets.danger_button}.get(style, widgets.secondary_button)
            kwargs = {"width": 110, "height": 36}
            make(row, text, lambda v=value: self._choose(v), **kwargs).pack(side="left", padx=(8, 0))
        self.geometry(f"{width}x1")
        self.after(30, self._present, parent, width)

    def _choose(self, value) -> None:
        self.result = value
        self.destroy()

    def _present(self, parent, width: int) -> None:
        try:
            self.update_idletasks()
            height = self.winfo_reqheight()
            x = parent.winfo_rootx() + max(0, (parent.winfo_width() - width) // 2)
            y = parent.winfo_rooty() + max(0, (parent.winfo_height() - height) // 3)
            self.geometry(f"{width}x{height}+{x}+{y}")
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass


def ask(parent, title: str, message: str, ok: str = "OK", cancel: str = "Cancel", danger: bool = False) -> bool:
    dialog = _Dialog(parent, title, message, [(cancel, False, "secondary"), (ok, True, "danger" if danger else "primary")])
    parent.wait_window(dialog)
    return bool(dialog.result)


def notify(parent, title: str, message: str, ok: str = "OK") -> None:
    dialog = _Dialog(parent, title, message, [(ok, True, "primary")])
    parent.wait_window(dialog)
