#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=========================================="
echo " K Downloader - macOS"
echo "=========================================="

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10+ is required: https://www.python.org/downloads/"
  exit 1
fi

python3 -m pip install --upgrade pip
python3 -m pip install -r src/requirements.txt pyinstaller

ICONSET="build/kaushan.iconset"
mkdir -p "$ICONSET"
python3 - <<'PY'
from PIL import Image
from pathlib import Path
im = Image.open("assets/k_downloader_logo.png").convert("RGBA")
sizes = {
 "icon_16x16.png":16, "icon_16x16@2x.png":32,
 "icon_32x32.png":32, "icon_32x32@2x.png":64,
 "icon_128x128.png":128, "icon_128x128@2x.png":256,
 "icon_256x256.png":256, "icon_256x256@2x.png":512,
 "icon_512x512.png":512,
}
out=Path("build/kaushan.iconset")
for name,size in sizes.items():
    im.resize((size,size), Image.Resampling.LANCZOS).save(out/name)
PY
iconutil -c icns "$ICONSET" -o assets/k_downloader.icns

rm -rf build dist release/macos
mkdir -p release/macos

python3 -m PyInstaller --noconfirm --clean --windowed \
  --name "K Downloader" \
  --icon "assets/k_downloader.icns" \
  --add-data "assets/k_downloader_logo.png:." \
  --collect-all customtkinter \
  --collect-all imageio_ffmpeg \
  --collect-all yt_dlp \
  --hidden-import tkinter \
  --hidden-import tkinter.filedialog \
  --hidden-import tkinter.messagebox \
  src/playlist_downloader.py

APP="dist/K Downloader.app"

# Optional Developer ID signing. Set APPLE_SIGNING_IDENTITY to use it.
if [[ -n "${APPLE_SIGNING_IDENTITY:-}" ]]; then
  codesign --force --deep --options runtime --timestamp \
    --sign "$APPLE_SIGNING_IDENTITY" "$APP"
  echo "Signed app with Developer ID."
else
  echo "NOTE: App is unsigned. Gatekeeper may show an unidentified-developer warning."
fi

# Create drag-and-drop DMG.
DMG="release/macos/K-Downloader-2.3.1-$(uname -m).dmg"
hdiutil create -volname "K Downloader" \
  -srcfolder "$APP" -ov -format UDZO "$DMG"

echo
echo "Created: $DMG"
echo "For public distribution without Gatekeeper warnings, sign and notarize with an Apple Developer ID."
