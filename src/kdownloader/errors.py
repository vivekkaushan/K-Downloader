"""Turn raw yt-dlp / network / OS errors into clear messages for users."""

from __future__ import annotations

import re
from dataclasses import dataclass

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


@dataclass(frozen=True)
class FriendlyError:
    code: str
    message: str
    retryable: bool = False
    detail: str = ""


def clean_text(text: str) -> str:
    text = _ANSI.sub("", str(text or "")).strip()
    for prefix in ("ERROR: ", "ERROR:"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    # drop yt-dlp's "[youtube] abc123: " style prefix
    text = re.sub(r"^\[[\w:\-\+ ]+\]\s*[\w\-]{0,20}:?\s*", "", text, count=1)
    first = text.splitlines()[0] if text else ""
    return first.strip()


_RULES = (
    ("cancelled", False, ("stopped by user", "download cancelled"),
     "Stopped."),
    ("private", False, ("private video", "private playlist", "this playlist is private",
                        "playlist does not exist", "playlist is private"),
     "This video or playlist is private. K Downloader can't access private content."),
    ("login", False, ("sign in to confirm", "confirm your age", "age-restricted", "age restricted",
                      "members-only", "members only", "join this channel", "requires payment",
                      "login required", "sign in to view"),
     "This content needs a sign-in, membership or payment. K Downloader doesn't bypass access "
     "controls, so it can't be downloaded."),
    ("drm", False, ("drm protected", "drm-protected", "protected by drm"),
     "This video is protected by DRM and can't be downloaded."),
    ("region", False, ("not available in your country", "blocked it in your country",
                       "blocked in your country", "geo restricted", "geo-restricted",
                       "not made this video available in your country"),
     "This video isn't available in your region."),
    ("unavailable", False, ("video unavailable", "has been removed", "been terminated",
                            "no longer available", "this video is not available",
                            "video has been deleted", "does not exist", "copyright"),
     "This video is unavailable (it may have been removed or made private)."),
    ("live", False, ("live event will begin", "is live", "live stream"),
     "Live streams can't be downloaded. Try again once the stream has ended."),
    ("invalid_url", False, ("unsupported url", "is not a valid url", "invalid url", "no video formats"),
     "That link isn't supported or doesn't contain a downloadable video."),
    ("ffmpeg", False, ("ffmpeg is not installed", "ffprobe and ffmpeg not found",
                       "ffmpeg not found", "avconv"),
     "FFmpeg is missing, so this format can't be converted. Reinstall K Downloader or pick "
     "'Best available'."),
    ("disk_full", False, ("no space left", "errno 28", "not enough space", "disk full"),
     "The drive is full. Free some space or choose another folder."),
    ("permission", False, ("permission denied", "errno 13", "read-only file system", "access is denied"),
     "K Downloader can't write to that folder. Choose a different download folder."),
    ("rate_limit", True, ("429", "too many requests", "rate limit"),
     "Too many requests right now. Wait a minute and retry."),
    ("network", True, ("timed out", "timeout", "temporary failure", "connection reset",
                       "connection aborted", "connection refused", "network is unreachable",
                       "name or service not known", "getaddrinfo", "failed to resolve",
                       "urlopen error", "unable to download", "remote end closed",
                       "incompleteread", "http error 5", "ssl", "eof occurred",
                       "no address associated", "nodename nor servname", "transporterror",
                       "network error", "unable to connect"),
     "Network problem. Check your internet connection and retry; partly downloaded files are resumed."),
)


def classify_error(exc_or_text) -> FriendlyError:
    raw = str(exc_or_text or "")
    if isinstance(exc_or_text, BaseException):
        raw = f"{type(exc_or_text).__name__}: {exc_or_text}" if not str(exc_or_text) else str(exc_or_text)
        # include the cause chain: yt-dlp wraps network errors
        cause = exc_or_text.__cause__ or exc_or_text.__context__
        if cause is not None:
            raw += " | " + str(cause)
    lowered = raw.lower()
    detail = clean_text(raw)
    for code, retryable, needles, message in _RULES:
        if any(n in lowered for n in needles):
            return FriendlyError(code, message, retryable, detail)
    short = detail or "Something went wrong."
    return FriendlyError("unknown", f"The download failed: {short}", False, detail)
