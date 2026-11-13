"""Scraper configuration. Secrets come from the environment, never from this file."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "Suki"

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("SUKI_DATA_DIR", REPO_ROOT / "data"))
CATALOG_DIR = Path(__file__).resolve().parent / "catalog"
# Raw PDFs are cached here and kept out of git (see .gitignore); Actions caches this folder.
PDF_CACHE_DIR = Path(os.environ.get("SUKI_PDF_CACHE", REPO_ROOT / ".cache" / "pdfs"))

USER_AGENT = (
    f"{APP_NAME}-price-monitor/1.0 (+open-source scraper of public DA daily price index PDFs; "
    "one request per report per day)"
)
HTTP_TIMEOUT = 60
# Pause between downloads during backfill, in seconds.
POLITE_DELAY = float(os.environ.get("SUKI_POLITE_DELAY", "0.5"))

# --- MIMAROPA (Google Drive) -------------------------------------------------
# Root folder per year. A new year means a new root folder: add it here.
# Verified 2026-11-13 (the ID in the original notes had "I" where Drive has "l").
MIMAROPA_ROOT_FOLDER_IDS: dict[int, str] = {
    2026: "1R8xdHxL18BM0y7ZfU4EzTDGSWMlQXIFa",
}
GOOGLE_DRIVE_API_KEY = os.environ.get("GOOGLE_DRIVE_API_KEY", "")

# --- NCR (da.gov.ph) ------------------------------------------------------------
NCR_URL_TEMPLATE = (
    "https://www.da.gov.ph/wp-content/uploads/{upload_year}/{upload_month:02d}/"
    "Daily-Price-Index-{month_name}-{day}-{year}.pdf"
)

# --- Run health -------------------------------------------------------------------
# Exit non-zero when no new file has been found for this many consecutive days.
MAX_DAYS_WITHOUT_NEW_FILE = 5

# --- Supabase / Web Push (alerts) -------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
# "mailto:" address or https URL identifying the sender to push services.
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "")
APP_URL = os.environ.get("SUKI_APP_URL", "/")

REGIONS = [
    {"id": "mimaropa", "name": "MIMAROPA", "status": "daily", "source": "DA MIMAROPA AMAD", "hasRange": True},
    {"id": "ncr", "name": "NCR (Metro Manila)", "status": "daily", "source": "DA Bantay Presyo", "hasRange": False},
    {"id": "car", "name": "CAR (Cordillera)", "status": "unavailable"},
    {"id": "ilocos", "name": "Ilocos Region", "status": "unavailable"},
    {"id": "cagayan-valley", "name": "Cagayan Valley", "status": "unavailable"},
    {"id": "central-luzon", "name": "Central Luzon", "status": "unavailable"},
    {"id": "calabarzon", "name": "CALABARZON", "status": "unavailable"},
]
ACTIVE_REGIONS = [r["id"] for r in REGIONS if r["status"] == "daily"]
