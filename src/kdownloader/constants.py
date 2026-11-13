"""Brand constants and shared application metadata."""

APP_NAME = "K Downloader"
PUBLISHER = "KAUSHAN"
__version__ = "3.0.0"

FACEBOOK_URL = "https://www.facebook.com/KaushanOfficial"
FACEBOOK_DISPLAY = "facebook.com/KaushanOfficial"
REPO_URL = "https://github.com/vivekkaushan/K-Downloader"
RELEASES_URL = REPO_URL + "/releases"
# A genuine endpoint: the latest published GitHub release. It is only contacted
# when the user presses "Check for updates" (never automatically).
UPDATE_API_URL = "https://api.github.com/repos/vivekkaushan/K-Downloader/releases/latest"

LOGO_FILE = "k_downloader_logo.png"
ICON_FILE = "k_downloader.ico"
CONFIG_DIR_NAME = ".k_downloader"

# Statuses used by the download engine and UI.
MIN_FREE_BYTES = 200 * 1024 * 1024
