"""A fast scrolling list that only draws the rows currently on screen.

Playlists can hold thousands of videos; creating a widget per row would make the
window sluggish, so rows are painted on a canvas on demand. Each row is a plain
dict supplied by ``provider(index)``.

Row keys used by the column kinds:
  text    row[key]; optional row[key + "_color"]
  check   row["check"] (bool)
  status  row["status"] text, row["status_color"], row["progress"] (None or 0..1)
"""

from __future__ import annotations

import sys
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from . import theme


@dataclass
class Column:
    key: str
    width: int = 0              # 0 = flexible column (shares the remaining width)
    kind: str = "text"          # text | check | status
    anchor: str = "w"
    muted: bool = False
    bold: bool = False


class VirtualList(ctk.CTkFrame):
    def __init__(self, master, columns: List[Column], provider: Callable[[int], dict], count: Callable[[], int],
                 row_height: int = 46, on_toggle: Optional[Callable[[int], None]] = None,
                 on_select: Optional[Callable[[int], None]] = None,
                 on_double: Optional[Callable[[int], None]] = None, empty_text: str = "Nothing here yet."):
        super().__init__(master, fg_color=theme.INSET, corner_radius=12, border_width=1, border_color=theme.BORDER)
        self.columns = columns
        self._provider, self._count = provider, count
        self._row_h = row_height
        self.on_toggle, self.on_select, self.on_double = on_toggle, on_select, on_double
        self.empty_text = empty_text
        self.selected: Optional[int] = None
        self._hover: Optional[int] = None
        self._redraw_pending = False
        self._fit_cache: Dict[tuple, str] = {}
        self._region: Optional[tuple] = None
        self._view: Optional[tuple] = None
        try:
            self._scale = float(self._get_widget_scaling())
        except Exception:
            self._scale = 1.0

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, highlightthickness=0, bd=0, bg=theme.resolve(theme.INSET))
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(6, 0), pady=6)
        self.scrollbar = ctk.CTkScrollbar(self, command=self.canvas.yview, height=0)
        self.scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 4), pady=6)
        self.canvas.configure(yscrollcommand=self._on_yscroll, yscrollincrement=max(1, int(self._row_h * self._scale / 2)))

        base = tkfont.nametofont("TkDefaultFont").actual("family")
        px = lambda size: -max(1, int(round(size * self._scale)))  # noqa: E731
        self._fonts = {
            "main": tkfont.Font(family=base, size=px(13)),
            "bold": tkfont.Font(family=base, size=px(13), weight="bold"),
            "small": tkfont.Font(family=base, size=px(12)),
            "small_bold": tkfont.Font(family=base, size=px(11), weight="bold"),
        }
        self.canvas.bind("<Configure>", lambda e: self.refresh())
        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<Double-Button-1>", self._double)
        self.canvas.bind("<Motion>", self._motion)
        self.canvas.bind("<Leave>", self._leave)
        self.canvas.bind("<Enter>", self._enter)

    # -- public ----------------------------------------------------------

    def refresh(self) -> None:
        """Repaint soon (coalesces bursts of updates)."""
        if not self._redraw_pending:
            self._redraw_pending = True
            self.after_idle(self._redraw)

    def reset_scroll(self) -> None:
        self.canvas.yview_moveto(0)
        self.selected = None
        self.refresh()

    def _set_appearance_mode(self, mode_string):  # CustomTkinter hook
        super()._set_appearance_mode(mode_string)
        try:
            self.canvas.configure(bg=theme.resolve(theme.INSET))
        except tk.TclError:
            return
        self.refresh()

    # -- geometry --------------------------------------------------------

    @property
    def _rh(self) -> int:
        return max(20, int(self._row_h * self._scale))

    def _layout(self, width: int):
        pad = int(10 * self._scale)
        fixed = sum(int(c.width * self._scale) for c in self.columns if c.width)
        flex = [c for c in self.columns if not c.width]
        flex_w = max(int(80 * self._scale), (width - fixed - pad * 2) // max(1, len(flex)))
        x, spans = pad, []
        for c in self.columns:
            w = int(c.width * self._scale) if c.width else flex_w
            spans.append((c, x, x + w))
            x += w
        return spans

    def _row_at(self, y: float) -> Optional[int]:
        index = int(self.canvas.canvasy(y) // self._rh)
        return index if 0 <= index < self._count() else None

    # -- drawing ---------------------------------------------------------

    def _on_yscroll(self, first, last) -> None:
        self.scrollbar.set(first, last)
        if (first, last) != self._view:   # avoid a repaint loop when only the region was re-set
            self._view = (first, last)
            self.refresh()

    def _fit(self, text: str, font_key: str, max_w: int) -> str:
        key = (text, font_key, max_w)
        cached = self._fit_cache.get(key)
        if cached is not None:
            return cached
        font = self._fonts[font_key]
        result = text
        if font.measure(text) > max_w:
            lo, hi = 0, len(text)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if font.measure(text[:mid] + "…") <= max_w:
                    lo = mid
                else:
                    hi = mid - 1
            result = text[:lo].rstrip() + "…"
        if len(self._fit_cache) > 4000:
            self._fit_cache.clear()
        self._fit_cache[key] = result
        return result

    def _redraw(self) -> None:
        self._redraw_pending = False
        try:
            c = self.canvas
            width, height = max(1, c.winfo_width()), max(1, c.winfo_height())
        except tk.TclError:
            return
        total = self._count()
        rh = self._rh
        region = (0, 0, width, max(total * rh, height))
        if region != self._region:
            self._region = region
            c.configure(scrollregion=region)
        c.delete("all")
        res = theme.resolve
        if total == 0:
            c.create_text(width // 2, height // 2, text=self.empty_text, fill=res(theme.MUTED),
                          font=self._fonts["main"], width=max(100, width - 40), justify="center")
            return
        top = c.canvasy(0)
        first = max(0, int(top // rh))
        last = min(total - 1, int((top + height) // rh))
        spans = self._layout(width)
        s = self._scale
        for i in range(first, last + 1):
            y0 = i * rh
            row = self._provider(i)
            if i == self.selected:
                c.create_rectangle(0, y0, width, y0 + rh, fill=res(theme.SELECTED), outline="")
            elif i == self._hover:
                c.create_rectangle(0, y0, width, y0 + rh, fill=res(theme.HOVER_ROW), outline="")
            c.create_line(0, y0 + rh - 1, width, y0 + rh - 1, fill=res(theme.BORDER))
            cy = y0 + rh // 2
            for col, x0, x1 in spans:
                if col.kind == "check":
                    size = int(18 * s)
                    bx, by = x0 + int(4 * s), cy - size // 2
                    if row.get("check"):
                        c.create_rectangle(bx, by, bx + size, by + size, fill=res(theme.PRIMARY), outline=res(theme.PRIMARY))
                        c.create_line(bx + size * .22, by + size * .52, bx + size * .43, by + size * .72,
                                      bx + size * .78, by + size * .30, fill="#FFFFFF", width=max(2, int(2 * s)))
                    else:
                        c.create_rectangle(bx, by, bx + size, by + size, fill="", outline=res(theme.MUTED), width=1)
                elif col.kind == "status":
                    pad = int(8 * s)
                    text = self._fit(str(row.get("status", "")), "small_bold", x1 - x0 - pad)
                    color = res(row.get("status_color", theme.MUTED))
                    progress = row.get("progress")
                    if progress is None:
                        c.create_text(x0, cy, text=text, anchor="w", fill=color, font=self._fonts["small_bold"])
                    else:
                        c.create_text(x0, cy - int(8 * s), text=text, anchor="w", fill=color, font=self._fonts["small_bold"])
                        bar_w, bar_h = x1 - x0 - pad, max(3, int(5 * s))
                        by = cy + int(7 * s)
                        c.create_rectangle(x0, by, x0 + bar_w, by + bar_h, fill=res(theme.TRACK), outline="")
                        fill_w = int(bar_w * max(0.0, min(1.0, progress)))
                        if fill_w > 0:
                            c.create_rectangle(x0, by, x0 + fill_w, by + bar_h, fill=res(theme.PRIMARY), outline="")
                else:
                    font_key = "bold" if col.bold else ("small" if col.muted else "main")
                    pad = int(8 * s)
                    text = self._fit(str(row.get(col.key, "")), font_key, x1 - x0 - pad)
                    color = res(row.get(col.key + "_color", theme.MUTED if col.muted else theme.TEXT))
                    sub = row.get(col.key + "_sub")
                    if sub and col.anchor == "w":
                        c.create_text(x0, cy - int(9 * s), text=text, anchor="w", fill=color, font=self._fonts[font_key])
                        c.create_text(x0, cy + int(10 * s), anchor="w", font=self._fonts["small"],
                                      text=self._fit(str(sub), "small", x1 - x0 - pad),
                                      fill=res(row.get(col.key + "_sub_color", theme.MUTED)))
                    elif col.anchor == "e":
                        c.create_text(x1 - pad, cy, text=text, anchor="e", fill=color, font=self._fonts[font_key])
                    elif col.anchor == "center":
                        c.create_text((x0 + x1) // 2, cy, text=text, anchor="center", fill=color, font=self._fonts[font_key])
                    else:
                        c.create_text(x0, cy, text=text, anchor="w", fill=color, font=self._fonts[font_key])

    # -- interaction -----------------------------------------------------

    def _click(self, event) -> None:
        index = self._row_at(event.y)
        if index is None:
            return
        check = next(((x0, x1) for col, x0, x1 in self._layout(self.canvas.winfo_width()) if col.kind == "check"), None)
        if check and check[0] <= event.x <= check[1] and self.on_toggle:
            self.on_toggle(index)
        else:
            self.selected = index
            self.refresh()
            if self.on_select:
                self.on_select(index)

    def _double(self, event) -> None:
        index = self._row_at(event.y)
        if index is not None and self.on_double:
            self.on_double(index)

    def _motion(self, event) -> None:
        index = self._row_at(event.y)
        if index != self._hover:
            self._hover = index
            self.refresh()

    def _leave(self, _event) -> None:
        self._hover = None
        self.refresh()
        self.canvas.unbind_all("<MouseWheel>")
        self.canvas.unbind_all("<Button-4>")
        self.canvas.unbind_all("<Button-5>")

    def _enter(self, _event) -> None:
        self.canvas.bind_all("<MouseWheel>", self._wheel)
        self.canvas.bind_all("<Button-4>", self._wheel)
        self.canvas.bind_all("<Button-5>", self._wheel)

    def _wheel(self, event) -> None:
        if getattr(event, "num", None) == 4:
            units = -2
        elif getattr(event, "num", None) == 5:
            units = 2
        elif sys.platform == "darwin":
            units = -int(event.delta)
        else:
            units = -2 if event.delta > 0 else 2
        self.canvas.yview_scroll(units, "units")
