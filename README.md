# K Downloader

**K Downloader** by **KAUSHAN** downloads YouTube playlists and single videos as MP4 or MP3 on macOS (Intel and Apple Silicon) and Windows 10/11. Everything runs on your computer. There is no account, no tracking and no ads.

- Fetch a playlist, see titles and durations, select all/none or individual videos
- MP4 up to 360p / 480p / 720p / 1080p / best, and MP3 at 128 / 192 / 320 kbps / best
- Per-video and overall progress, speed, ETA, stop / cancel / retry failed
- Choose and remember a download folder; existing files are never overwritten
- Download history, settings, dark and light themes
- Optional, never required: **Follow KAUSHAN** on https://www.facebook.com/KaushanOfficial

Download only content you own or have permission to save. K Downloader does not bypass private videos, sign-in requirements, paywalls or DRM.

## Install

Installers are built by GitHub Actions (**Actions → Build K Downloader installers → latest run → Artifacts**, or the **Releases** page for tagged versions).

| Platform | File |
|---|---|
| Windows 10/11 | `K-Downloader-Windows-Setup.exe` |
| macOS, Intel | `K-Downloader-macOS-Intel.dmg` |
| macOS, Apple Silicon (M1 and later) | `K-Downloader-macOS-Apple-Silicon.dmg` |

The builds are **not code-signed and not notarized** (that needs paid developer accounts), so your system will warn you the first time:

- **Windows:** SmartScreen shows "Windows protected your PC". Choose **More info → Run anyway**.
- **macOS:** drag K Downloader to Applications, then right-click it and choose **Open** (once). If macOS still refuses, open **System Settings → Privacy & Security** and choose **Open Anyway**.

## Run from source

Python 3.10 or newer with Tk is required.

```bash
python3 -m pip install -r src/requirements.txt
python3 src/playlist_downloader.py
```

Run the tests (a virtual display such as `xvfb-run` is used for the UI test on Linux):

```bash
python3 -m unittest discover -s tests
```

## Build installers

Use GitHub Actions: push to `main`, or run the workflow manually. Pushing a tag such as `v3.0.0` also publishes a GitHub Release containing all three installers.

Local builds: `windows\build_windows.bat` (Windows) or `bash macos/build_macos.command` (macOS, builds on the Mac's own architecture). See `docs/BUILDING.md`.

## Project layout

```
src/playlist_downloader.py   launcher
src/kdownloader/             application (engine/, config, history, ui/)
assets/                      logo and icon
windows/  macos/             packaging scripts
tests/                       unit, integration and UI smoke tests
docs/                        building, signing, troubleshooting
```

## Privacy

Settings and history are stored in `~/.k_downloader` on your computer. The app contacts the internet only to read the links you give it, to download them, and, only when you press **Check for updates**, GitHub's public releases API.

## Licences

See `THIRD-PARTY-NOTICES.md`.
