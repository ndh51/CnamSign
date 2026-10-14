import os
from dotenv import load_dotenv

load_dotenv()

# Identifiants uniques
EMAIL = os.getenv("EMAIL") or os.getenv("IMAP_USER") or os.getenv("CNAM_USER") or ""
PASSWORD = os.getenv("PASSWORD") or os.getenv("IMAP_PASSWORD") or os.getenv("CNAM_PASSWORD") or ""
PIN_CODE = os.getenv("PIN_CODE") or os.getenv("CNAM_PIN") or ""

# Configuration IMAP / Réseau
IMAP_HOST = os.getenv("IMAP_HOST", "outlook.office365.com")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "30"))
OUTLOOK_FOLDER = os.getenv("OUTLOOK_FOLDER", "Emargements")

# Options Playwright
HEADLESS = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")
DEBUG_SCREENSHOTS = os.getenv("DEBUG_SCREENSHOTS", "false").lower() in ("true", "1", "yes")

# Alias de compatibilité
IMAP_USER = EMAIL
IMAP_PASSWORD = PASSWORD
CNAM_USER = EMAIL
CNAM_PASSWORD = PASSWORD
CNAM_PIN = PIN_CODE

def validate_config():
    missing = []
    if not EMAIL:
        missing.append("EMAIL")
    if not PASSWORD:
        missing.append("PASSWORD")
    if not PIN_CODE:
        missing.append("PIN_CODE")
    if missing:
        raise ValueError(f"Variables manquantes dans .env : {', '.join(missing)}")
