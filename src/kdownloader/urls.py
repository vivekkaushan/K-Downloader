"""URL validation. Rejects obviously wrong input before any network request."""

from __future__ import annotations

from typing import NamedTuple
from urllib.parse import parse_qs, urlparse

YOUTUBE_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
    "youtu.be", "www.youtu.be", "youtube-nocookie.com", "www.youtube-nocookie.com",
}


class UrlCheck(NamedTuple):
    ok: bool
    url: str
    message: str = ""


def _normalize(raw: str) -> str:
    url = (raw or "").strip()
    if url and "://" not in url and (url.startswith("www.") or url.split("/")[0] in YOUTUBE_HOSTS):
        url = "https://" + url
    return url


def _parse(raw: str):
    url = _normalize(raw)
    if not url:
        return None, UrlCheck(False, "", "Paste a link first.")
    if any(ch.isspace() for ch in url):
        return None, UrlCheck(False, url, "That doesn't look like a valid link (it contains spaces).")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or "." not in parsed.netloc:
        return None, UrlCheck(False, url, "That doesn't look like a valid web link. It should start with https://")
    return parsed, UrlCheck(True, url)


def check_playlist_url(raw: str) -> UrlCheck:
    parsed, result = _parse(raw)
    if parsed is None:
        return result
    host = (parsed.hostname or "").lower()
    if host in YOUTUBE_HOSTS:
        playlist_id = (parse_qs(parsed.query).get("list") or [""])[0]
        if not playlist_id:
            return UrlCheck(False, result.url,
                            "This link has no playlist in it. Use a playlist link (it contains "
                            "'list='), or use the Single Video Downloader for one video.")
        if playlist_id in ("WL", "LL"):
            return UrlCheck(False, result.url,
                            "Watch Later and Liked videos are private lists that need your login, "
                            "which K Downloader doesn't use. Open a public or unlisted playlist instead.")
    return result


def check_video_url(raw: str) -> UrlCheck:
    parsed, result = _parse(raw)
    if parsed is None:
        return result
    host = (parsed.hostname or "").lower()
    if host in YOUTUBE_HOSTS:
        path = parsed.path.strip("/")
        query = parse_qs(parsed.query)
        has_video = bool(query.get("v")) or host.endswith("youtu.be") and bool(path) or \
            path.split("/")[0] in ("shorts", "live", "embed", "v")
        if not has_video:
            if query.get("list"):
                return UrlCheck(False, result.url,
                                "This is a playlist link. Use the Playlist Downloader page for it.")
            return UrlCheck(False, result.url, "This link doesn't point to a single video.")
    return result
