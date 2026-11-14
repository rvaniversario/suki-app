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

# Every region. `powerbi` is the REGION label in the Bantay Presyo dashboard. All regions use the
# same method: the regional price is the median across the region's markets. The PDF scrapers
# (MIMAROPA Drive, NCR da.gov.ph) are kept but not run; set `pdf: True` on a region to use one.
_BP = "DA Bantay Presyo"
REGIONS = [
    {"id": "ncr", "name": "NCR (Metro Manila)", "powerbi": "NCR (NATIONAL CAPITAL REGION)"},
    {"id": "car", "name": "CAR (Cordillera)", "powerbi": "CAR (CORDILLERA ADMINISTRATIVE REGION)"},
    {"id": "ilocos", "name": "Ilocos Region", "powerbi": "REGION I (ILOCOS REGION)"},
    {"id": "cagayan-valley", "name": "Cagayan Valley", "powerbi": "REGION II (CAGAYAN VALLEY)"},
    {"id": "central-luzon", "name": "Central Luzon", "powerbi": "REGION III (CENTRAL LUZON)"},
    {"id": "calabarzon", "name": "CALABARZON", "powerbi": "REGION IV-A (CALABARZON)"},
    {"id": "mimaropa", "name": "MIMAROPA", "powerbi": "REGION IV-B (MIMAROPA)"},
    {"id": "bicol", "name": "Bicol Region", "powerbi": "REGION V (BICOL REGION)"},
    {"id": "western-visayas", "name": "Western Visayas", "powerbi": "REGION VI (WESTERN VISAYAS)"},
    {"id": "central-visayas", "name": "Central Visayas", "powerbi": "REGION VII (CENTRAL VISAYAS)"},
    {"id": "eastern-visayas", "name": "Eastern Visayas", "powerbi": "REGION VIII (EASTERN VISAYAS)"},
    {"id": "zamboanga", "name": "Zamboanga Peninsula", "powerbi": "REGION IX (ZAMBOANGA PENINSULA)"},
    {"id": "northern-mindanao", "name": "Northern Mindanao", "powerbi": "REGION X (NORTHERN MINDANAO)"},
    {"id": "davao", "name": "Davao Region", "powerbi": "REGION XI (DAVAO REGION)"},
    {"id": "soccsksargen", "name": "SOCCSKSARGEN", "powerbi": "REGION XII (SOCCSKSARGEN)"},
    {"id": "caraga", "name": "Caraga", "powerbi": "REGION XIII (Caraga)"},
    {"id": "barmm", "name": "BARMM", "powerbi": "BARMM (Bangsamoro Autonomous Region of Muslim Mindanao)"},
]
for _r in REGIONS:
    if not _r.get("pdf"):
        _r.update(status="daily", source=f"{_BP} (median of markets)", hasRange=True, pdf=False)
    _r["markets"] = True
REGION_BY_ID = {r["id"]: r for r in REGIONS}
ACTIVE_REGIONS = [r["id"] for r in REGIONS if r["status"] == "daily"]

# --- Bantay Presyo Power BI (per-market prices, all regions) ------------------------
# Resource key from the public report URL (SPEC section 4.3). The model id is looked up at run time.
POWERBI_RESOURCE_KEY = "f5edb48b-b77c-4154-ae2b-9a2c1a783c37"
