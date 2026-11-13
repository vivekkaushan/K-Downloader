"""Optional first-run welcome. Nothing is required; closing it is always fine."""

from __future__ import annotations

from ..config import mark_welcome_seen
from . import dialogs, widgets, theme
import customtkinter as ctk


class WelcomeDialog(dialogs._Dialog):
    def __init__(self, parent):
        super().__init__(parent, "Welcome to K Downloader",
                         "Paste a playlist link, pick the videos and a quality, and download. Everything stays on your computer: "
                         "no account, no tracking.\n\nIf you like the app, you're welcome to follow KAUSHAN on Facebook. "
                         "It's entirely optional.",
                         [("Follow KAUSHAN", "follow", "secondary"), ("Get started", "go", "primary")], width=480)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _choose(self, value) -> None:
        if value == "follow":
            from ..constants import FACEBOOK_URL
            widgets.open_url(FACEBOOK_URL)
        self._close()

    def _close(self) -> None:
        mark_welcome_seen()
        self.destroy()


def show_if_first_run(parent) -> None:
    from ..config import welcome_seen
    if not welcome_seen():
        WelcomeDialog(parent)
