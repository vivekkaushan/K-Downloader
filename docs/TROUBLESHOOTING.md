# Troubleshooting

**Windows warns "Windows protected your PC".** The installer is unsigned. Choose More info → Run anyway.

**macOS says the app can't be opened.** The app is unsigned. Right-click → Open, or System Settings → Privacy & Security → Open Anyway.

**"That doesn't look like a YouTube playlist link."** Use a link containing `list=`.

**Video unavailable, private or region-restricted.** K Downloader does not bypass access controls. Only public videos you may access can be downloaded.

**Downloads fail with a network message.** The app retries automatically; use **Retry failed** once your connection is back. Partial files resume.

**"Not enough free space."** Pick another folder in Settings or free up disk space.

**MP3 or best quality unavailable.** FFmpeg wasn't found. It is bundled with the installers; when running from source, run `pip install imageio-ffmpeg`.

**YouTube changed and downloads suddenly fail.** Update the bundled downloader engine by installing the newest release, or from source: `pip install -U yt-dlp`.

**Reset everything.** Close the app and delete the `.k_downloader` folder in your home folder.
