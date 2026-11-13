# Suki — wet market price monitor

A mobile-first PWA showing which fish, pork, chicken and beef are a good buy today, from Department of
Agriculture daily price reports, with a suggested weekly buying plan. See [SPEC.md](SPEC.md).

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
python -m scraper run --region all                          # daily: last 10 days, new files only
python -m scraper backfill --region mimaropa --from 2026-01-01
python -m scraper rebuild --region all                      # re-parse cached PDFs after a catalog change
```

Raw PDFs are cached in `.cache/pdfs/` (git-ignored; the Actions cache keeps them between runs).

## Configuration

| Where | Name | Needed for |
|---|---|---|
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
