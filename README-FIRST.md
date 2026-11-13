# K Downloader — Public Distribution Kit

Product name: **K Downloader**
Version: **2.3.1**  
Publisher: **KAUSHAN**  
Facebook: https://www.facebook.com/KaushanOfficial

This kit prepares native installer builds for macOS and Windows using the supplied K Downloader logo.

## Included
- K Downloader application source
- First-launch welcome screen with Facebook follow link and user acknowledgement
- Supplied logo and platform icons
- PyInstaller build scripts
- macOS `.app` + `.dmg` build script
- Windows application folder + Inno Setup `Setup.exe` recipe
- Bundled FFmpeg runtime through `imageio-ffmpeg`

## Build for macOS
Build on a Mac (PyInstaller does not reliably cross-compile native apps):
1. Install Python 3.10+.
2. Run `bash macos/build_macos.command`.
3. The `.dmg` is created in `release/macos/`.
4. For public distribution without Gatekeeper warnings, sign and notarize with an Apple Developer ID. This requires your Apple Developer account.

## Build for Windows
Build on Windows 10/11:
1. Install Python 3.10+.
2. Run `windows\build_windows.bat`.
3. Install Inno Setup: https://jrsoftware.org/isinfo.php
4. Open `windows\K-Downloader-Setup.iss` and choose Build > Compile.
5. The Setup.exe is created in `release\windows\`.

## End-user experience
Once built, users can install the software without installing Python or FFmpeg separately. Test each installer on a clean machine before publishing. Windows code signing is recommended to reduce SmartScreen warnings.

## Responsible use
Use only for videos you own, have permission to download, or are otherwise legally permitted to save. Respect YouTube's Terms of Service and copyright law. The app does not bypass DRM, paywalls, private-account restrictions, or access controls.


## First-launch Facebook welcome screen
On first launch, K Downloader shows a welcome screen with a button to open the KAUSHAN Facebook page. The user can tick an acknowledgement and continue. This acknowledgement is stored locally in `~/.k_downloader/welcome_acknowledged.json`, so the prompt is not shown again on subsequent launches. Facebook does not provide this app with a reliable way to verify an individual page follow; the checkbox is an honour-system acknowledgement and must not be described as verified.


## Build installers automatically with GitHub Actions
A workflow is included at `.github/workflows/main.yml`. It builds:
- Windows x64 installer: `K-Downloader-Windows-Setup.exe`
- macOS Intel: `K-Downloader-macOS-Intel.dmg`
- macOS Apple Silicon: `K-Downloader-macOS-Apple-Silicon.dmg`

To use it:
1. Create a private or public GitHub repository and upload the contents of this kit.
2. Open the repository's Actions tab.
3. Select **Build K Downloader installers**.
4. Click **Run workflow**.
5. When all jobs finish, open the workflow run and download the three installer artifacts (each is a zip containing one installer).

The workflow uses GitHub-hosted Windows and Mac machines, so you do not need to own both operating systems to run the builds. These builds are currently unsigned. Public Mac distribution still needs Apple Developer ID signing and notarization; Windows signing is also recommended. The GitHub Actions workflow does not perform signing or notarization.

Version in this build kit: 2.3.1.
