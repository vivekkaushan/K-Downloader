from __future__ import annotations

import customtkinter as ctk

from ...constants import FACEBOOK_URL, PUBLISHER, REPO_URL, RELEASES_URL, __version__
from .. import widgets
from .base import Page


class AboutPage(Page):
    title = "About K Downloader"

    def __init__(self, parent, ctx):
        super().__init__(parent, ctx)
        self.header()
        card = widgets.card(self)
        card.grid(row=1, column=0, sticky="ew")
        card.grid_columnconfigure(1, weight=1)
        logo = widgets.logo_image(96)
        ctk.CTkLabel(card, text="" if logo else "K", image=logo).grid(row=0, column=0, rowspan=3, padx=22, pady=22)
        widgets.label(card, "K Downloader", 22, "bold").grid(row=0, column=1, sticky="sw", pady=(22, 0))
        widgets.muted(card, f"Version {__version__}  ·  by {PUBLISHER}", 12).grid(row=1, column=1, sticky="nw")
        widgets.muted(card, "A playlist and video downloader for macOS and Windows. Everything runs on your computer: "
                            "no account, no tracking, no ads.", 12, wraplength=520, justify="left", anchor="w").grid(
            row=2, column=1, sticky="nw", pady=(6, 22), padx=(0, 22))

        notes = widgets.card(self)
        notes.grid(row=2, column=0, sticky="ew", pady=12)
        for text in ("Only download content you own or have permission to save. K Downloader does not bypass private videos, "
                     "sign-in requirements, paywalls or DRM.",
                     "Built with yt-dlp, FFmpeg, CustomTkinter and Python. Their licences are listed in THIRD-PARTY-NOTICES.md "
                     "in the project."):
            widgets.muted(notes, text, 12, wraplength=700, justify="left", anchor="w").pack(anchor="w", padx=18, pady=(12, 0))
        row = ctk.CTkFrame(notes, fg_color="transparent")
        row.pack(anchor="w", padx=14, pady=(8, 12))
        widgets.text_button(row, "Source code", lambda: widgets.open_url(REPO_URL), width=100).pack(side="left")
        widgets.text_button(row, "Releases", lambda: widgets.open_url(RELEASES_URL), width=80).pack(side="left")

        widgets.FacebookCard(self).grid(row=3, column=0, sticky="w")
