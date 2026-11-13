# Building K Downloader

## With GitHub Actions (recommended)
`.github/workflows/main.yml` runs on push to `main`, on tags `v*`, and manually.

1. **test** – unit, integration and headless UI tests on Ubuntu.
2. **build-windows** – PyInstaller, then Inno Setup → `K-Downloader-Windows-Setup.exe`.
3. **build-macos** – native runners: `macos-15-intel` (Intel) and `macos-15` (Apple Silicon) → one DMG each, with an Applications shortcut.
4. **release** – only for tags starting with `v`; attaches the three installers to a GitHub Release. This is the only job with write permission.

Artifacts are kept by GitHub for 90 days. An installer is only available when its job shows a green check.

## Locally
- Windows: install Python 3.10+ and Inno Setup, then run `windows\build_windows.bat`.
- macOS: run `bash macos/build_macos.command`. PyInstaller builds for the Mac you are on; build on an Intel Mac for Intel and on Apple Silicon for Apple Silicon.

## Signing and notarization
Not configured, so builds are unsigned and **not notarized**.
- macOS: set `APPLE_SIGNING_IDENTITY` for `build_macos.command` to sign locally. Notarization needs an Apple Developer account and `xcrun notarytool`.
- Windows: sign `K-Downloader-Windows-Setup.exe` with `signtool` and a code-signing certificate.
Store certificates and passwords as GitHub encrypted secrets, never in the repository.
