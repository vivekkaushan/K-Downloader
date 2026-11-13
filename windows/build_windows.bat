@echo off
setlocal
cd /d "%~dp0\.."
echo ==========================================
echo  K Downloader - Windows
echo ==========================================

where py >nul 2>nul
if errorlevel 1 (
  echo Python 3.10+ is required. Install it from https://www.python.org/downloads/
  pause
  exit /b 1
)

py -m pip install --upgrade pip
py -m pip install -r src\requirements.txt pyinstaller

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

py -m PyInstaller --noconfirm --clean --windowed ^
  --name "K Downloader" ^
  --icon "assets\k_downloader.ico" ^
  --add-data "assets\k_downloader_logo.png;." ^
  --collect-all customtkinter ^
  --collect-all imageio_ffmpeg ^
  --collect-all yt_dlp ^
  --hidden-import tkinter ^
  --hidden-import tkinter.filedialog ^
  --hidden-import tkinter.messagebox ^
  src\playlist_downloader.py

if errorlevel 1 (
  echo Build failed. Review the error above.
  pause
  exit /b 1
)

echo.
echo Build complete:
echo dist\K Downloader\
echo.
echo To create a user-friendly Setup.exe:
echo 1. Install Inno Setup from https://jrsoftware.org/isinfo.php
echo 2. Open windows\K-Downloader-Setup.iss in Inno Setup Compiler
echo 3. Click Build ^> Compile
echo.
pause
