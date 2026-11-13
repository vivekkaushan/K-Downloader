"""Optional update check against the project's GitHub releases.

Only runs when the user presses "Check for updates". Sends no identifying data.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import NamedTuple, Optional, Tuple

from .constants import RELEASES_URL, UPDATE_API_URL, __version__


class UpdateResult(NamedTuple):
    status: str  # "up_to_date" | "available" | "no_releases" | "error" | "disabled"
    latest: Optional[str] = None
    url: str = RELEASES_URL
    message: str = ""


def parse_version(text: str) -> Tuple[int, ...]:
    nums = re.findall(r"\d+", text or "")
    return tuple(int(n) for n in nums[:4]) or (0,)


def check_for_updates(current: str = __version__, endpoint: str = UPDATE_API_URL,
                      timeout: float = 8.0) -> UpdateResult:
    if not endpoint:
        return UpdateResult("disabled", message="No update endpoint is configured.")
    request = urllib.request.Request(endpoint, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"K-Downloader/{current}",
    })
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # nosec - fixed https endpoint
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return UpdateResult("no_releases", message="No releases have been published yet.")
        return UpdateResult("error", message=f"The update server answered with an error ({exc.code}).")
    except (urllib.error.URLError, OSError, ValueError):
        return UpdateResult("error", message="Couldn't reach the update server. Check your internet connection.")
    tag = str(data.get("tag_name") or "")
    url = str(data.get("html_url") or RELEASES_URL)
    if not tag:
        return UpdateResult("no_releases", message="No releases have been published yet.")
    if parse_version(tag) > parse_version(current):
        return UpdateResult("available", latest=tag.lstrip("vV"), url=url,
                            message=f"Version {tag.lstrip('vV')} is available.")
    return UpdateResult("up_to_date", latest=tag.lstrip("vV"), url=url,
                        message="You're using the latest version.")
