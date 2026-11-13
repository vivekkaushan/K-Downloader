"""Small formatting helpers shared by the engine and the UI."""

from __future__ import annotations

from datetime import datetime
from typing import Optional


def format_duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "—"
    try:
        n = int(seconds)
    except (TypeError, ValueError):
        return "—"
    if n < 0:
        return "—"
    h, rem = divmod(n, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def format_bytes(value: Optional[float]) -> str:
    if not value or value < 0:
        return "—"
    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return "—"


def format_speed(bytes_per_second: Optional[float]) -> str:
    if not bytes_per_second or bytes_per_second <= 0:
        return "—"
    return format_bytes(bytes_per_second) + "/s"


def format_eta(seconds: Optional[float]) -> str:
    if seconds is None or seconds < 0:
        return "—"
    return format_duration(seconds)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def format_when(iso_text: Optional[str], now: Optional[datetime] = None) -> str:
    """'Today 17:31', 'Yesterday 09:02' or '13 Nov 2026'."""
    try:
        when = datetime.fromisoformat(str(iso_text))
    except (TypeError, ValueError):
        return "—"
    now = now or datetime.now()
    days = (now.date() - when.date()).days
    if days == 0:
        return f"Today {when:%H:%M}"
    if days == 1:
        return f"Yesterday {when:%H:%M}"
    return f"{when.day} {when:%b %Y}"
