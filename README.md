# Suki — wet market price monitor

A mobile-first PWA showing which goods are a good buy today (fish, meat, eggs, rice, vegetables, fruit,
spices and more), for every region, from Department of Agriculture price data, with a suggested weekly
buying plan for fish and meat and an optional "My market" view of one market's prices. See [SPEC.md](docs/SPEC.md).

```
app/        React 18 + Vite + TypeScript PWA
scraper/    Python scraper (parsers, catalog, analytics, alerts) + tests
data/       generated JSON, committed by the scraper
supabase/   SQL migration and RLS for accounts and push subscriptions
.github/    scrape (daily), deploy (GitHub Pages), test
```

## Run locally

```sh
# app (serves ../data at /data)
cd app && npm install && npm run dev

# tests
cd app && npm test && npm run test:e2e        # vitest; Playwright smoke at 390/820/1440 px + offline
python -m pytest scraper/tests -q

# scraper
pip install -r scraper/requirements.txt
python -m scraper run --region all                          # daily: re-reads the last 21 days
python -m scraper backfill --region all --days 365           # fill an empty data/ (needed for npm run dev)
```

## Deploy

One Docker container serves the app and keeps its own prices current; no rebuild or redeploy is
needed for new prices. No price data is committed (`data/` is git-ignored).

```sh
docker compose up -d --build        # http://localhost:8080
```

- nginx serves the built app; `/data` is served from the `/data` volume.
- The scraper runs in the same container. On first start (empty volume) it fetches the last
  `HISTORY_DAYS` days (default 365, about 10 minutes for all 17 regions); until then a region shows
  "could not load prices". After that it runs every day at 10:00 Manila (`REFRESH_UTC`, default 2),
  re-reading only the last 21 days. History stays in the volume, so it is never fetched again.
- Container hosts (VPS, Railway, Render, Fly.io): build from the `Dockerfile`, mount a persistent
  volume at `/data`, and set `PORT` if the host requires a specific one.

## Configuration

| Where | Name | Needed for |
|---|---|---|
| Container env | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` (`PRICE_DB=0` turns it off) | Permanent copy of the price data in Supabase (`scraper/db.py`, migration `20261115000000_prices.sql`). Each run saves what it changed; a container with an empty volume restores from it instead of re-scraping. Seed once with `docker compose exec suki python -m scraper push`. The app never reads the database. |
| Container env | `GEMINI_API_KEY` (free tier, default) or `OPENAI_API_KEY`; `AI_PROVIDER` (`gemini`/`openai`/`off`), `GEMINI_MODEL`, `OPENAI_MODEL`, `AI_WEB_SEARCH`, `AI_DAILY_REQUESTS`, `AI_DAILY_TOKENS` | AI weekly notes per region and per market (`scraper/insights.py`, `scraper/ai.py`). Off without a key. At most one note request per region per day, only when its prices change, plus a web search only when a good moved 15%+ in a week; a daily cap stops it, and running out of quota pauses it until the next day. |
| Actions secret | `GOOGLE_DRIVE_API_KEY` | Drive API listing. Optional: without it the public folder view is used. |
| Actions secret | `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `VAPID_PRIVATE_KEY` | Sending price drop alerts |
| Actions variable | `VAPID_SUBJECT` (`mailto:` or https URL), `APP_URL` | Alerts |
| Actions variable | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `VAPID_PUBLIC_KEY` | Accounts and alerts in the built app |

Without any of these the app still works fully: prices, ranking, plan, settings, offline. Account and
alert settings show "not set up" instead.

Backend setup: create a Supabase project, run `supabase/migrations/*.sql`, enable the email (magic link)
and Google providers, and add the app URL plus `/settings` to the auth redirect URLs. Generate VAPID
keys once (`npx web-push generate-vapid-keys`).

Hosting: `deploy.yml` publishes to GitHub Pages (enable Pages → "GitHub Actions"). For another static
host, build `app/` with `npm run build` and serve `app/dist`.

## Data sources

Every region uses the same source and method: the DA **Bantay Presyo** market monitoring. A region's
price for a good is the median across its markets, and "My market" shows one market's own prices.

The older PDF scrapers (MIMAROPA from Google Drive, NCR from da.gov.ph) are still in `scraper/` but are
not run. Setting `pdf: True` on a region in `scraper/config.py` switches it back to its PDF report.

**Bantay Presyo** is the DA's public Power BI dashboard (`scraper/sources/powerbi.py`, SPEC section 4.3).
It uses undocumented endpoints, so any failure is logged as "source unavailable" and never fails a run.
The scraper only ever queries the price table and never the `ENCODER` column or the contacts table
(`tbl_csw`); a guard in the query builder and a test enforce this.

- One query per region per run, re-reading the last 21 days because prices are often entered late.
- Goods are mapped by `COMMODITY` through `scraper/catalog/bantaypresyo.yaml` (91 goods).
- A market price outside 0.4×–2.5× of the item's 90-day regional median is rejected and logged.
- Regional point for date d: median of each market's latest price from the
  7 days up to d, needing at least 2 markets.
- Every good shows its newest available price, however old, with that price's date. Markets are
  never hidden; each market price carries its date.
- Output: `data/{region}/markets.json` (markets, newest date) and `data/{region}/markets/{code}.json`
  (newest price per good).
- The source swaps latitude and longitude for many markets; the scraper puts them back.

## Data notes (from the 2026 backfill)

- **MIMAROPA** (304 reports, Jan 1 – Nov 12): the full 14-section layout only started in **November**.
  Until October the report had a short meat list (`FISH`, `LIVESTOCK & POULTRY PRODUCTS`: Bangus,
  Tilapia, Galunggong, Pork Ham, Pork Belly, Beef Rump/Brisket, Whole Chicken). The catalog maps both
  layouts to the same items, so the year-long history covers those; November-only cuts (pork chop, beef
  chuck, chicken parts…) show "Not enough history yet" until they have 14 days.
- `Pork Ham` (old) is mapped to kasim and `Pork Belly` to liempo; ranges and prices line up.
- The 4th `Whole Chicken, Local` row continues the old single `Whole Chicken` series (same range), so
  that occurrence is featured. Other duplicate rows are stored under auto ids and left unlabelled.
- Real-file quirks handled: dates without "As of" (Oct 1–6), a page dated Nov 8 inside the Nov 4 file
  (warning, first page wins), `#DIV/0!` / `#N/A` cells, `ml` units.
- **NCR** (315 reports, weekends included): the layout changed in late October (new section names such
  as `FISHERIES AND SEAFOOD`, `PORK`, `CHICKEN`, and new commodity names). Both map to the same ids. Old
  files print the chicken brand in the specification column; "Fully Dressed" there corresponds to the
  new "Unbranded" row. January files close the date with `]`; cells like `n/as`, `+n/a`, `#DIV/0!` are
  treated as not available. Two files lack the pork header and log warnings.
- The 2026 MIMAROPA root folder ID in the spec had one misread character (`I` → `l`); the verified ID is
  in `scraper/config.py`.

## Before release

- `app/src/locales/fil.json` is marked unreviewed; have a native speaker check it.
- Privacy notice text is in the locale files (`privacy.*`); review against the Data Privacy Act before
  turning accounts on.
