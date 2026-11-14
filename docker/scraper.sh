#!/bin/sh
# Scraper container: fill an empty data volume, then refresh once a day.
#
#   HISTORY_DAYS   days of history to fetch on first start (default 365; rankings need 90)
#   REFRESH_UTC    hour of the daily run, UTC (default 2 = 10:00 Manila)
# With Supabase configured, an empty volume is first restored from the database (scraper/db.py).
set -u

DATA="${SUKI_DATA_DIR:-/data}"
MARKER="$DATA/.backfill-done"   # nginx never serves dotfiles
mkdir -p "$DATA"

if [ ! -f "$MARKER" ]; then
  # Empty volume: restore from Supabase if it has our data, then catch up the last days.
  python -m scraper restore --region all
  restored=$?
  if [ "$restored" -eq 0 ]; then
    echo "scraper: restored from Supabase; catching up recent prices"
    python -m scraper run --region all || true
    date -u +%Y-%m-%dT%H:%M:%SZ > "$MARKER"
  fi
fi

if [ ! -f "$MARKER" ]; then
  echo "scraper: no data yet, fetching the last ${HISTORY_DAYS:-365} days for every region"
  if python -m scraper backfill --region all --days "${HISTORY_DAYS:-365}"; then
    date -u +%Y-%m-%dT%H:%M:%SZ > "$MARKER"
  else
    echo "scraper: first fetch failed; retrying in 15 minutes"
    sleep 900
    exec "$0"
  fi
fi

while true; do
  wait=$(python - <<'EOF'
import os
from datetime import datetime, timedelta, timezone
now = datetime.now(timezone.utc)
run = now.replace(hour=int(os.environ.get("REFRESH_UTC", "2")), minute=0, second=0, microsecond=0)
if run <= now:
    run += timedelta(days=1)
print(int((run - now).total_seconds()))
EOF
)
  echo "scraper: next run in ${wait}s"
  sleep "$wait"
  python -m scraper run --region all || echo "scraper: run exited with $?"
done
