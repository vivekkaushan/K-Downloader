"""Brand palette. Colours are (light, dark) pairs understood by CustomTkinter."""

from __future__ import annotations

import customtkinter as ctk

# Brand colours (dark theme values come straight from the KAUSHAN brand sheet).
BG = ("#F5F2FB", "#100820")          # deep navy/purple
SURFACE = ("#FFFFFF", "#1B1030")     # dark purple surface
SURFACE_2 = ("#EFEAF9", "#261849")
SURFACE_HOVER = ("#E4DCF5", "#32205E")
SIDEBAR = ("#EBE5F8", "#0B0517")
INSET = ("#F1ECFA", "#150C28")
BORDER = ("#DDD5EE", "#33244F")
TRACK = ("#DDD5EE", "#33244F")
SELECTED = ("#E4DAF7", "#2C1B52")
HOVER_ROW = ("#F0EAFB", "#201339")
TEXT = ("#1B1030", "#FFFFFF")
MUTED = ("#6A6382", "#A7A0B5")       # secondary text
PRIMARY = "#7041C7"                  # primary purple
PRIMARY_HOVER = ("#5B32B0", "#8454D9")
ACCENT = ("#6B3FC0", "#A78BFA")      # lavender accent
WHITE = "#FFFFFF"
SUCCESS = ("#15803D", "#4ADE80")
WARNING = ("#B45309", "#FBBF24")
DANGER = ("#B91C1C", "#F87171")
DANGER_BG = ("#FDECEC", "#3A1520")
DANGER_HOVER = ("#F9D5D5", "#4D1B29")

_fonts: dict = {}


def mode_index() -> int:
    return 1 if ctk.get_appearance_mode() == "Dark" else 0


def resolve(color) -> str:
    """Pick the concrete colour for the current appearance mode."""
    if isinstance(color, (tuple, list)):
        return color[mode_index()]
    return color


def font(size: int = 13, weight: str = "normal") -> ctk.CTkFont:
    key = (size, weight)
    if key not in _fonts:
        _fonts[key] = ctk.CTkFont(size=size, weight=weight)
    return _fonts[key]


def apply_mode(mode: str) -> None:
    ctk.set_appearance_mode(mode if mode in ("dark", "light", "system") else "dark")
