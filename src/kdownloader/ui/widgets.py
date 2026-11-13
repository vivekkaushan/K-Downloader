"""Reusable styled widgets."""

from __future__ import annotations

import io
import webbrowser
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image

from .. import paths
from ..constants import FACEBOOK_DISPLAY, FACEBOOK_URL, LOGO_FILE
from . import theme

_logo_cache: dict = {}


def open_url(url: str) -> None:
    try:
        webbrowser.open(url)
    except Exception:
        pass


def logo_image(size: int) -> Optional[ctk.CTkImage]:
    """The KAUSHAN logo, or None if the file is missing."""
    if size in _logo_cache:
        return _logo_cache[size]
    image = None
    path = paths.resource_path(LOGO_FILE)
    if path:
        try:
            with Image.open(path) as im:
                im = im.convert("RGBA")
                image = ctk.CTkImage(light_image=im.copy(), dark_image=im.copy(), size=(size, size))
        except Exception:
            image = None
    _logo_cache[size] = image
    return image


def label(parent, text: str = "", size: int = 13, weight: str = "normal", color=theme.TEXT, **kw) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=theme.font(size, weight), text_color=color, **kw)


def muted(parent, text: str = "", size: int = 12, **kw) -> ctk.CTkLabel:
    return label(parent, text, size, "normal", theme.MUTED, **kw)


def card(parent, **kw) -> ctk.CTkFrame:
    kw.setdefault("corner_radius", 16)
    return ctk.CTkFrame(parent, fg_color=theme.SURFACE, border_width=1, border_color=theme.BORDER, **kw)


def primary_button(parent, text: str, command: Optional[Callable] = None, width: int = 150, height: int = 40, **kw):
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=height, corner_radius=10,
                         fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER, text_color=theme.WHITE,
                         text_color_disabled=("#B9A8DC", "#7F6BAA"), font=theme.font(13, "bold"), **kw)


def secondary_button(parent, text: str, command: Optional[Callable] = None, width: int = 110, height: int = 34, **kw):
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=height, corner_radius=9,
                         fg_color=theme.SURFACE_2, hover_color=theme.SURFACE_HOVER, text_color=theme.TEXT,
                         text_color_disabled=theme.MUTED, border_width=1, border_color=theme.BORDER,
                         font=theme.font(12, "bold"), **kw)


def danger_button(parent, text: str, command: Optional[Callable] = None, width: int = 110, height: int = 34, **kw):
    return ctk.CTkButton(parent, text=text, command=command, width=width, height=height, corner_radius=9,
                         fg_color=theme.DANGER_BG, hover_color=theme.DANGER_HOVER, text_color=theme.DANGER,
                         text_color_disabled=theme.MUTED, border_width=1, border_color=theme.BORDER,
                         font=theme.font(12, "bold"), **kw)


def text_button(parent, text: str, command: Optional[Callable] = None, **kw):
    return ctk.CTkButton(parent, text=text, command=command, height=28, corner_radius=8,
                         fg_color="transparent", hover_color=theme.SURFACE_2, text_color=theme.ACCENT,
                         font=theme.font(12, "bold"), **kw)


def entry(parent, textvariable=None, placeholder: str = "", height: int = 42, **kw) -> ctk.CTkEntry:
    return ctk.CTkEntry(parent, textvariable=textvariable, placeholder_text=placeholder, height=height,
                        corner_radius=10, border_width=1, border_color=theme.BORDER, fg_color=theme.INSET,
                        text_color=theme.TEXT, placeholder_text_color=theme.MUTED, font=theme.font(13), **kw)


def option_menu(parent, values, command=None, width: int = 200, **kw) -> ctk.CTkOptionMenu:
    return ctk.CTkOptionMenu(parent, values=list(values), command=command, width=width, height=34,
                             corner_radius=9, fg_color=theme.SURFACE_2, button_color=theme.PRIMARY,
                             button_hover_color=theme.PRIMARY_HOVER, text_color=theme.TEXT,
                             dropdown_fg_color=theme.SURFACE, dropdown_text_color=theme.TEXT,
                             dropdown_hover_color=theme.SURFACE_HOVER, font=theme.font(12), **kw)


def segmented(parent, values, command=None, **kw) -> ctk.CTkSegmentedButton:
    return ctk.CTkSegmentedButton(parent, values=list(values), command=command, height=34,
                                  fg_color=theme.SURFACE_2, selected_color=theme.PRIMARY,
                                  selected_hover_color=theme.PRIMARY_HOVER, unselected_color=theme.SURFACE_2,
                                  unselected_hover_color=theme.SURFACE_HOVER, text_color=theme.TEXT,
                                  font=theme.font(12, "bold"), **kw)


def progress_bar(parent, height: int = 8, **kw) -> ctk.CTkProgressBar:
    bar = ctk.CTkProgressBar(parent, height=height, corner_radius=height, fg_color=theme.TRACK,
                             progress_color=theme.PRIMARY, **kw)
    bar.set(0)
    return bar


class Banner(ctk.CTkLabel):
    """One-line status message under a form (info / success / warning / error)."""

    COLORS = {"info": theme.MUTED, "success": theme.SUCCESS, "warn": theme.WARNING, "error": theme.DANGER}

    def __init__(self, parent, wraplength: int = 760, **kw):
        super().__init__(parent, text="", anchor="w", justify="left", wraplength=wraplength,
                         font=theme.font(12), text_color=theme.MUTED, **kw)

    def show(self, text: str, kind: str = "info") -> None:
        self.configure(text=text, text_color=self.COLORS.get(kind, theme.MUTED))

    def clear(self) -> None:
        self.configure(text="")


class StatCard(ctk.CTkFrame):
    def __init__(self, parent, title: str, value: str = "0", hint: str = ""):
        super().__init__(parent, fg_color=theme.SURFACE, corner_radius=14, border_width=1, border_color=theme.BORDER)
        self.grid_columnconfigure(0, weight=1)
        label(self, title.upper(), 10, "bold", theme.MUTED).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 0))
        self.value = label(self, value, 26, "bold")
        self.value.grid(row=1, column=0, sticky="w", padx=16, pady=(0, 0))
        self.hint = muted(self, hint, 11)
        self.hint.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 12))

    def set(self, value: str, hint: Optional[str] = None) -> None:
        self.value.configure(text=value)
        if hint is not None:
            self.hint.configure(text=hint)


class Thumbnail(ctk.CTkLabel):
    """Preview image box. Shows the KAUSHAN logo until a picture arrives."""

    def __init__(self, parent, size=(128, 72)):
        self._size = size
        self._pic = None
        super().__init__(parent, text="", width=size[0], height=size[1], corner_radius=10,
                         fg_color=theme.INSET)
        self.clear()

    def clear(self) -> None:
        logo = logo_image(min(self._size) - 16)
        self._pic = logo
        self.configure(image=logo, text="" if logo else "K")

    def set_bytes(self, data: Optional[bytes]) -> None:
        if not data:
            return self.clear()
        try:
            with Image.open(io.BytesIO(data)) as im:
                im = im.convert("RGB")
                im.thumbnail((self._size[0] * 2, self._size[1] * 2))
                img = ctk.CTkImage(light_image=im.copy(), dark_image=im.copy(),
                                   size=(self._size[0], int(self._size[0] * im.height / im.width))
                                   if im.width else self._size)
            # fit inside the box, keep aspect ratio
            w, h = img.cget("size")
            if h > self._size[1]:
                w, h = int(w * self._size[1] / h), self._size[1]
                img.configure(size=(w, h))
            self._pic = img
            self.configure(image=img, text="")
        except Exception:
            self.clear()


class FacebookCard(ctk.CTkFrame):
    """The 'Follow KAUSHAN' section. Purely optional; opens the default browser."""

    def __init__(self, parent, compact: bool = False):
        super().__init__(parent, fg_color=theme.SURFACE, corner_radius=16, border_width=1, border_color=theme.BORDER)
        self.grid_columnconfigure(0, weight=1)
        label(self, "Enjoying K Downloader?", 15 if not compact else 14, "bold").grid(
            row=0, column=0, sticky="w", padx=18, pady=(16, 2))
        muted(self, "Follow KAUSHAN on Facebook for updates, creative projects and more.", 12,
              wraplength=300 if compact else 420, justify="left").grid(row=1, column=0, sticky="w", padx=18)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=2, column=0, sticky="w", padx=18, pady=(12, 4))
        primary_button(row, "Follow KAUSHAN", lambda: open_url(FACEBOOK_URL), width=160, height=36).pack(side="left")
        muted(self, f"{FACEBOOK_DISPLAY} · optional — the app works the same either way", 10).grid(
            row=3, column=0, sticky="w", padx=18, pady=(0, 14))


class Footer(ctk.CTkFrame):
    def __init__(self, parent, version: str):
        super().__init__(parent, fg_color="transparent", height=34)
        self.grid_columnconfigure(1, weight=1)
        label(self, "Powered by KAUSHAN", 11, "bold", theme.ACCENT).grid(row=0, column=0, sticky="w")
        muted(self, f"K Downloader v{version}", 11).grid(row=0, column=1, sticky="e", padx=(0, 14))
        text_button(self, "Follow on Facebook", lambda: open_url(FACEBOOK_URL), width=130).grid(row=0, column=2, sticky="e")
