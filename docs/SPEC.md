# SPEC: Suki — wet market price monitor (PWA)

"Suki" is a working name. Keep it in one constant so it can be renamed.

## 1. Goal

A mobile-first web app that shows which fish, pork, chicken and beef are a good buy today, based on government price reports, and turns that into a suggested weekly buying plan.

It answers two questions for someone going to the palengke:

1. Which goods are cheap today compared with their usual price? (ranked list)
2. So how much of each should I buy this week? (for example: fish 2 kg, pork 1 kg, chicken ½ kg, beef 0 because it is much pricier than usual)

There is no official API. Data comes from scraping public PDF price reports published by the Philippine Department of Agriculture (DA).

## 2. Scope

### In scope (v1)

- Daily scraper for two regions: MIMAROPA and NCR.
- Price history per commodity, per region.
- Ranked "best buys today" list with category filters.
- Item detail with price history chart and low / average / high.
- Weekly plan with suggested kilos and an estimated total.
- Manual region picker, remembered on the device.
- Settings: usual weekly kilos, optional weekly budget, goods to track.
- Light and dark themes.
- Two languages: English and Filipino.
- Price drop alerts by push notification.
- Optional accounts, to keep settings across devices.
- Installable PWA with offline support.
- Responsive layout: phone, tablet, laptop, desktop.

### Out of scope (v1)

- Location auto-detect. Region is picked manually.
- User-entered prices.
- Sharing a plan between different people (one account = one person's settings).
- AI/LLM in the pipeline. The PDFs are text-based and parse deterministically. An LLM fallback for layout changes can be added later; do not build it now.
- Server-side rendering, SEO pages.

## 3. Architecture

Static site plus scheduled scraper for all price data. A small hosted backend (Supabase) is used only for the two features that need one: accounts and push notifications. The app must work fully without signing in and without notifications; never block price browsing on the backend being reachable.

```
GitHub Actions (daily cron)
  └─ scraper (Python)
       ├─ downloads new PDFs (Google Drive API for MIMAROPA, HTTPS for NCR)
       ├─ parses them into normalized rows
       ├─ computes baselines and scores
       └─ commits JSON files to /data  ──►  static host  ──►  React PWA fetches JSON
```

| Part | Choice | Why |
|---|---|---|
| Frontend | React 18 + Vite + TypeScript | No SSR or SEO need, so Next.js adds nothing here |
| PWA | `vite-plugin-pwa` (Workbox) | Manifest, service worker, offline cache |
| Routing | React Router | Three top-level views plus item detail |
| Styling | Plain CSS with custom properties, or CSS modules | Small app; tokens in section 9 |
| Charts | Hand-rolled SVG, or `recharts` if simpler | One line chart only |
| State | React state + `localStorage` for settings | No global store needed |
| Scraper | Python 3.12, `pdfplumber`, `requests` | Best PDF table tooling |
| Schedule | GitHub Actions cron | Free, no server |
| Backend | Supabase (Auth + Postgres with row-level security) | Accounts and push subscriptions only; free tier is enough |
| Push | Web Push with VAPID keys, sent from the scraper with `pywebpush` | No extra server; alerts go out right after new data lands |
| i18n | `react-i18next` (or an equivalent small dictionary) | Two languages, all strings in translation files |
| Hosting | Any static host (GitHub Pages, Netlify, Vercel, Cloudflare Pages) | Must serve over HTTPS for PWA install |

Repository layout:

```
/app            React + Vite PWA
/scraper        Python package + tests
/scraper/tests/fixtures   sample PDFs
/data           generated JSON, committed by the scraper
/.github/workflows/scrape.yml
/supabase       SQL migrations and RLS policies
docs/SPEC.md
```

## 4. Data sources

### 4.1 MIMAROPA (primary, verified)

- Publisher: DA MIMAROPA, Agribusiness and Marketing Assistance Division (AMAD).
- Report: "Daily Price Index — Consolidated Daily Retail Prices of Agri-fishery Commodities in MIMAROPA Region".
- Location: a Google Drive folder linked from `https://www.mimaropa.da.gov.ph/media-resources/daily-price-index`. Do not scrape that website; its TLS certificate is invalid. Go straight to Drive.
- Folder structure: `2026/` → `NOVEMBER 2026/` (month name in capitals + year) → `November 10, 2026.pdf` (one file per day, weekends included).
- History: month folders exist for January to November 2026.
- Lag: the newest file can be one to two days behind the calendar date.
- Folder IDs (read from screenshots, verify before use; put them in `scraper/config.py`):
  - 2026 root: `1R8xdHxL18BM0y7ZfU4EzTDGSWMIQXIFa` (unverified, may contain a misread character)
  - NOVEMBER 2026: `1SeoT7bcyagPHu2PCSJJdOG3dTLap27JV` (resolved without sign-in)
- Access: Google Drive API v3 with an API key (`files.list` with `'<folderId>' in parents`, then `files.get?alt=media`). Works only if the folders are shared as "anyone with the link". Verify this first; if it fails, stop and report rather than working around it.
- Yearly rollover: a new year means a new root folder ID. Make the root ID a config value and log a clear error when the current year's folder is missing.

#### Report format (from the November 10, 2026 file, 12 pages)

Text-based PDF (not scanned). Each page repeats a title block, then table rows:

```
COMMODITY | UNIT | PRICE RANGE: LOW | HIGH | AVERAGE PRICES | CURRENT PRICES (MODE)
```

Section header rows (no numbers), in order:
`IMPORTED COMMERCIAL RICE`, `LOCAL COMMERCIAL RICE`, `CORN PRODUCTS`, `LEGUMES`, `FISH PRODUCTS`, `BEEF PRODUCTS`, `PORK PRODUCTS`, `OTHER LIVESTOCK MEAT PRODUCTS`, `POULTRY PRODUCTS`, `LOWLAND VEGETABLES`, `HIGHLAND VEGETABLES`, `SPICES`, `FRUITS`, `OTHER BASIC COMMODITIES`.

Sample rows:

```
Tilapia                               kg   120.00   200.00   158.82   170.00
Pork Picnic Shoulder (Kasim), Local   kg   270.00   390.00   335.00   340.00
Bonito (Frigate Tuna)                 kg     -        -        -        -
```

Parsing rules and known quirks:

1. **Use AVERAGE as the price.** The MODE column is unreliable: several values fall outside their own low–high range (chicken thigh mode 110.00 with range 130–240; large egg mode 4.50 with range 8–10). Store mode, but never rank on it.
2. **Missing values** are a single `-` in all four columns. Store as null and exclude from ranking for that day.
3. **Duplicate commodity names.** Some names repeat within a section with different values, for example `Whole Chicken, Local` ×4, `Chicken Breast, Local` ×4, `Cooking Oil (Palm)` ×2. A distinguishing column appears to be missing from the PDF. Disambiguate by occurrence index within the section (`whole-chicken-local-1` … `-4`). The meaning of each variant is unknown; do not guess labels.
4. **Sections span pages.** A section header appears once; carry it across page breaks.
5. **Skip page furniture:** title block, column headers, and footer lines containing `facebook.com/amad4bmimaropa`.
6. **Skip the last page**, titled "Consolidated Daily Retail Prices of Cigarettes".
7. **Units** are `kg` or `pc` (eggs). Keep the unit; rank only `kg` items in v1.
8. **Date** comes from the line `As of November 10, 2026`. Cross-check it against the file name and fail the file on mismatch.
9. Figures are region-wide (five island provinces), so low–high ranges are wide. This is expected.

### 4.2 NCR (secondary)

- Publisher: DA, national site.
- Report: "Daily Price Index — National Capital Region (NCR) — Prevailing Retail Price of Agri-fishery Commodities in Selected Wet Markets".
- URL pattern (confirmed for 2026 files): `https://www.da.gov.ph/wp-content/uploads/{YYYY}/{MM}/Daily-Price-Index-{Month}-{D}-{YYYY}.pdf`, for example `.../2026/10/Daily-Price-Index-October-20-2026.pdf`.
- Format (seen only in search snippets, verify against a real file): columns `COMMODITY | SPECIFICATION | PREVAILING RETAIL PRICE PER UNIT`. One price per item, no low/high. `n/a` means not available.
- The `{MM}` upload folder may not match the report month for files uploaded late. On a 404, try the following month's folder.
- Build this parser second, after MIMAROPA works end to end. Download one real file into fixtures first and confirm the layout.

### 4.3 Bantay Presyo Power BI dashboard (optional, per-market prices — build last)

The DA publishes a national "Bantay Presyo Monitoring System" dashboard as a public Power BI report. It is the only source found with prices per market rather than per region, and it covers all regions.

- Report URL: `https://app.powerbi.com/view?r=eyJrIjoiZjVlZGI0OGItYjc3Yy00MTU0LWFlMmItOWEyYzFhNzgzYzM3IiwidCI6IjI1MzYzMDI3LTUyNjQtNGE1Mi04MmRjLTgzYWNiZTMwY2M4YiIsImMiOjEwfQ%3D%3D`
- Resource key (from the URL token): `f5edb48b-b77c-4154-ae2b-9a2c1a783c37`. Model id observed: `4925438` (look it up at run time, do not hard-code).
- The page loads data from `https://wabi-south-east-asia-api.analysis.windows.net/public/reports/` using `{key}/modelsAndExploration`, `conceptualschema` and `querydata`, with the header `X-PowerBI-ResourceKey: {key}`. These are internal, undocumented endpoints: they can change without notice and there is no official API. Isolate this fetcher behind an interface, and treat any failure as "source unavailable", never as a failed run.
- Price table: `bantaypresyo vw_mmprices (2)` with columns including `REGION`, `MARKET`, `MARKET_CODE`, `MARKET_LAT`, `MARKET_LONG`, `CATEGORY`, `COMMODITY`, `COMMODITY_CODE`, `UNIT`, `HIGH`, `LOW`, `PREVAILING`, `PRICE_AVERAGE`, `DATE_ENCODED`, `DATE_VERIFIED`.
- **Do not query any other table.** The same dataset exposes `bantaypresyo tbl_csw`, which holds company contact persons, phone numbers and email addresses. The scraper must never request it. Also do not store the `ENCODER` column from the price table.
- The date slider spans 2024-07-01 to the present, so there is more history here than in the MIMAROPA Drive folder.

Known problems, to measure before relying on it:

1. **Freshness varies by market.** On 2026-11-13 the dashboard's default date was 2026-11-03, and Puerto Princesa City New Public Market showed 2026-09-18. Record the latest date per market and show it in the app; hide a market whose latest date is more than 14 days old.
2. **Data-entry errors.** Seen on the dashboard: whole chicken high of 2,400, pork liempo high of 2,450, egg low of 0.50. Use `PREVAILING` as the price and reject a value outside 0.4×–2.5× the item's 90-day median for that region (log rejects).
3. **Commodity names differ** from the Drive PDFs ("Pork Ham (Kasim)" vs "Pork Picnic Shoulder (Kasim), Local"). Map them through the catalog to the same item ids.

Use in the app: a "My market" option under the region. When a market is chosen and has fresh data, show its prevailing price beside the regional average on the Item screen. Rankings and baselines stay on the regional series from 4.1 and 4.2, which is cleaner. Query only the selected regions, one small request per region per day.

First step for this source is a short investigation, reported before building: rows per day for MIMAROPA, latest date per market, and the share of rows rejected by the outlier rule.

**Change (2026-11-14):** built for every region and every good, not only "My market". Every region, MIMAROPA and NCR included, now ranks on the median across its markets (README, "Data sources"); the PDF scrapers of sections 4.1 and 4.2 are kept but not run. The catalogs gained eggs, rice, vegetables, fruits, spices and other basic goods; these are ranked like meat and fish but are not part of the weekly plan.

### 4.4 Scraping etiquette

- At most one run per day per source. Never re-download a file already processed.
- Keep raw PDFs out of git; cache them in the Actions cache or re-fetch on demand.
- Identify the scraper with a descriptive User-Agent.
- Show the source and report date in the app ("DA MIMAROPA AMAD, as of November 10").

## 5. Data model

Generated files, all under `/data`, all static JSON.

### `data/regions.json`

```json
[
  { "id": "mimaropa", "name": "MIMAROPA", "status": "daily", "source": "DA MIMAROPA AMAD", "hasRange": true },
  { "id": "ncr", "name": "NCR (Metro Manila)", "status": "daily", "source": "DA Bantay Presyo", "hasRange": false }
]
```

Other regions may be listed with `"status": "unavailable"` so the picker can show them greyed out.

### `data/{region}/latest.json`

Everything the Today and Plan screens need in one request.

```json
{
  "region": "mimaropa",
  "asOf": "2026-11-10",
  "generatedAt": "2026-11-12T01:05:00Z",
  "items": [
    {
      "id": "fish.tilapia",
      "name": "Tilapia",
      "category": "fish",
      "unit": "kg",
      "price": 158.82,
      "low": 120.0,
      "high": 200.0,
      "baseline": 163.4,
      "pctVsBaseline": -2.8,
      "status": "ok",
      "daysOfHistory": 87
    }
  ]
}
```

### `data/{region}/history/{itemId}.json`

```json
{ "id": "fish.tilapia", "points": [ { "d": "2026-11-09", "p": 160.1, "lo": 120, "hi": 200 } ] }
```

### `scraper/catalog/{region}.yaml`

Hand-maintained mapping from raw report rows to app items. This is where naming changes get absorbed.

```yaml
- raw: "Pork Picnic Shoulder (Kasim), Local"
  section: "PORK PRODUCTS"
  occurrence: 1
  id: pork.kasim
  name: "Pork kasim"
  category: pork
  featured: true
```

- `category` is one of `fish | pork | chicken | beef | other`.
- Only `featured: true` items appear in the ranked list by default. Start with roughly 6–10 per category that are priced on most days.
- Rows with no catalog entry are still stored under an auto-generated id and logged, never dropped silently.
- A catalogued row that disappears from a report must produce a warning in the run log.

## 6. Analytics

Computed by the scraper, not in the browser.

- **Price** = AVERAGE (MIMAROPA) or PREVAILING (NCR) for the report date.
- **Baseline ("usual price")** = median of that item's price over the trailing 90 calendar days, excluding the report date. Requires at least 14 data points; otherwise `baseline` is null and the item is shown unranked with "Not enough history yet".
- **Score** `pctVsBaseline = (price − baseline) / baseline × 100`, rounded to one decimal.
- **Status:**
  - `buy` when score ≤ −4
  - `skip` when score ≥ +5
  - `ok` otherwise
- **Ranking:** ascending by score (most below usual first). Do not rank by raw price; beef would always lose to chicken.

Keep the thresholds and the window as named constants.

### Weekly plan

Inputs, from user settings: usual kilos per week for each category. Defaults: fish 1, pork 1, chicken 1, beef 0.5.

For each category:

1. Pick the featured item with the lowest score.
2. Multiplier `m`:
   - score ≥ +10 → `m = 0` ("Skip this week")
   - otherwise `m = clamp(1 − 0.1 × score, 0.5, 2)` (so −8% gives 1.8, +5% gives 0.5)
3. Suggested kilos = usual × `m`, rounded to the nearest 0.25 kg.
4. Advice label: `Buy more` (m > 1.1), `Buy as usual`, `Buy less` (m < 0.9), `Skip this week` (m = 0).

Totals: estimated cost = Σ kilos × price. Also show the difference against the same kilos at baseline prices ("About ₱38 less than at usual prices").

The user can adjust each quantity with − / + steppers in 0.25 kg steps; adjustments persist in `localStorage` until the next report date.

**Weekly budget (optional setting).** When a budget is set and the estimated cost exceeds it, reduce quantities in 0.25 kg steps, always taking the next step from the plan item with the highest score (priciest against its usual), until the cost is at or under budget or every quantity is 0. Show a line on the Plan screen saying the plan was trimmed to fit the budget. Manual stepper changes are not trimmed; show an "over budget by ₱X" notice instead.

**Tracked goods (setting).** The ranked list and the plan consider only goods the user tracks. Default: the catalog's `featured` items. The plan picks from tracked items only; a category with no tracked items is left out of the plan.

These formulas are a first version. Keep them in one module with unit tests so they are easy to tune.

## 7. Screens

Navigation has three destinations: **Today**, **Plan**, **History**. Settings is a secondary screen, not a tab.

### Today (home)

- Header: app name, region pill (opens region picker), settings icon button, title "Best buys today", subtitle "Ranked by how far each price is below its usual".
- "As of {date}" line with the source name. If the report is more than 3 days old, show a visible stale-data notice.
- Category filter chips: All, Fish, Pork, Chicken, Beef.
- Ranked rows: rank number, name, price per kilo, status chip ("8% below usual" / "2% above usual"). Tapping a row opens the item screen.
- Items with no price today are hidden. Items without a baseline go in a separate unranked group at the bottom.

### Item

- Name, region, price per kilo, status chip.
- Where the region has range data: "₱120 to ₱200 across the region".
- Range toggle: 30 days / 90 days / 1 year.
- Line chart of price with a dashed baseline line. Gaps in data are gaps in the line, not interpolated.
- Low / Usual / High for the selected range.
- Button to add the suggested kilos to the plan.

### Plan

- Summary card: estimated total and difference against usual prices.
- One card per category: advice label, chosen item, price and line cost, quantity stepper, and a bar showing quantity relative to the largest quantity in the plan.
- Link to Settings to edit usual weekly kilos and budget.

### Settings

Reached from an icon button in the Today header on phone, and from a "Settings" item at the bottom of the rail (tablet) and in the sidebar (laptop, desktop). It is not a tab.

Eight settings, all stored in `localStorage` under one versioned key and applied immediately (no Save button). Items 1–4 are the shopping settings; 5–8 are grouped under an "App" heading:

1. **Region.** Shows the current region; "Change" opens the region picker.
2. **What you usually buy in a week.** One row per category (fish, pork, chicken, beef) with − / + steppers in 0.25 kg steps, minimum 0, and a total line. Defaults: 1, 1, 1, 0.5.
3. **Weekly budget (optional).** Peso amount; empty means no limit. Helper text explains that the plan cuts back the priciest-versus-usual goods first.
4. **Goods to track.** Opens a checklist of all catalogued items for the region, grouped by category, with search. Shows the count of tracked goods.

5. **Appearance.** Same as phone (default) / Light / Dark. See section 9.
6. **Language.** English / Filipino. See section 15.
7. **Price drop alerts.** Off by default. See section 16.
8. **Account.** "Sign in" when signed out; email and "Sign out" when signed in. See section 17.

The settings object: `{ v, region, usualKg: {fish, pork, chicken, beef}, budget, trackedIds, theme, language, alerts, updatedAt }`.

If stored settings are missing or unreadable (cleared browser data), fall back to defaults and show the region picker again; never crash. On first run, call `navigator.storage.persist()` to ask the browser not to evict the data.

### History

- Searchable list of all catalogued items for the region, grouped by category, each opening the Item screen.

### Region picker

- Bottom sheet on phone, dialog on larger screens.
- Radio list from `regions.json`: available regions show "Daily prices"; unavailable ones are disabled with "Not available yet".
- Shown automatically on first launch. Choice stored in `localStorage`.

### Install prompt

- Custom sheet: "Add Suki to your home screen", with two benefits (opens full screen; keeps last prices and the plan offline).
- Android/desktop Chromium: capture `beforeinstallprompt` and trigger it from the button.
- iOS Safari: no programmatic prompt exists; show the Share → "Add to Home Screen" instructions instead.
- Show after the second visit, never on first load. "Not now" suppresses it for 30 days.

## 8. Responsive behaviour

Mobile-first. One codebase, three layouts.

| Width | Layout |
|---|---|
| < 640px (phone) | Single column. Bottom tab bar. Ranked list as rows. |
| 640–1023px (tablet) | Left icon rail (88px). Today shows a plan summary strip and a two-column card grid. |
| ≥ 1024px (laptop, desktop) | Left sidebar (220px) with labels and an "Install app" button. Today shows a ranking table (rank, item, price, usual, against usual, this week) beside a right column holding the plan summary and a chart of the selected item. Content max-width 1160px. |

- Touch targets at least 44×44px.
- Wide tables scroll horizontally inside their own container; the page never scrolls sideways.
- Respect `env(safe-area-inset-*)` for the bottom tab bar when installed.

## 9. Visual design

Utilitarian, data-first. No gradients, no emoji. Light theme tokens first, dark theme below.

| Token | Value | Use |
|---|---|---|
| `--ground` | `#F4F6F3` | Page background |
| `--surface` | `#FFFFFF` | Cards, lists, nav |
| `--ink` | `#14211D` | Primary text |
| `--muted` | `#55635E` | Secondary text |
| `--line` | `#DDE3DF` | Borders |
| `--line-soft` | `#E7ECE9` | Row dividers |
| `--control-border` | `#C9D2CD` | Buttons, chips |
| `--primary` | `#0B5D51` | Primary actions, active nav, chart line |
| `--buy-bg` / `--buy-fg` | `#DDF0EA` / `#0B5D51` | "Below usual" chip |
| `--ok-bg` / `--ok-fg` | `#EBEFEC` / `#46534E` | Neutral chip |
| `--skip-bg` / `--skip-fg` | `#FCE9DA` / `#8F3A05` | "Above usual" chip, baseline line |

### Dark theme

Applied when the Appearance setting is Dark, or "Same as phone" and `prefers-color-scheme: dark`. Implement by swapping the same custom properties on `:root[data-theme="dark"]`; no component may hard-code a colour. Set `<meta name="theme-color">` to match the active theme.

| Token | Dark value |
|---|---|
| `--ground` | `#0F1614` |
| `--surface` | `#18211E` |
| `--ink` | `#E8EEEB` |
| `--muted` | `#9FB0A9` |
| `--line` | `#2A3632` |
| `--line-soft` | `#222D29` |
| `--control-border` | `#3A4843` |
| `--primary` | `#4FB5A3` (text on primary-filled buttons is `#0F1614`, not white) |
| `--buy-bg` / `--buy-fg` | `#17382F` / `#7FD3C2` |
| `--ok-bg` / `--ok-fg` | `#232D2A` / `#B4C2BC` |
| `--skip-bg` / `--skip-fg` | `#40260F` / `#F2A765` |

These dark values are a starting palette and have not been checked in a browser. Verify every text/background pair reaches 4.5:1 contrast and adjust where it does not. The summary card that is filled with `--primary` in light theme uses `--surface` with a `--primary` border in dark theme.

- Fonts: Inter (text), Space Grotesk (headings, prices, numerals). Self-host them so they work offline.
- Status is never colour alone: each chip also has an icon (down arrow, dash, up arrow) and text.
- Teal and orange are used instead of green and red for colour-blind safety.
- Radii: 16–18px cards, 12–14px buttons, full pill for chips.
- Currency: `₱` with two decimals for per-kilo prices, whole pesos for totals. Quantities as `2 kg`, `½ kg`, `¼ kg`.
- UI languages: English and Filipino (section 15), with local commodity names (bangus, galunggong, kasim, liempo) in both.

## 10. PWA requirements

- `manifest.webmanifest`: name, short name, `display: standalone`, theme colour `#0B5D51`, background `#F4F6F3`, icons 192, 512 and a maskable 512.
- Service worker via `vite-plugin-pwa`, `registerType: 'autoUpdate'`.
- Caching:
  - App shell and fonts: precache.
  - `/data/**`: stale-while-revalidate, so the last fetched prices show instantly and offline.
- Offline: the app opens and shows the last fetched data with a small "Offline — showing prices as of {date}" notice. The plan and settings work fully offline.
- Lighthouse PWA installability checks pass.

## 11. Scraper behaviour

- Entry point: `python -m scraper run --region mimaropa|ncr|all`.
- Backfill: `python -m scraper backfill --region mimaropa --from 2026-01-01`.
- Idempotent: keeps a manifest of processed files (`data/{region}/manifest.json`) and skips them.
- One bad file must not stop the run. Record the failure in the manifest with the reason and continue.
- After parsing, regenerate `latest.json` and affected `history/*.json`, then commit only if something changed.
- After a new report date is committed for a region, send price drop alerts for that region (section 16). A failure to send alerts must not fail the data update.
- Sanity checks per row, logged as warnings: low ≤ average ≤ high; price changed more than 40% from the previous data point.
- Exit non-zero if no new file has been found for 5 consecutive days, so the workflow shows as failing.

### GitHub Actions

- `scrape.yml`: cron once daily at 10:00 Asia/Manila (02:00 UTC), plus manual dispatch.
- Secrets: `GOOGLE_DRIVE_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `VAPID_PRIVATE_KEY`. Never commit them. The service role key is used only by the scraper, never shipped to the browser.
- Commits to `/data` on the default branch, which triggers the static host's deploy.

## 12. Testing

- **Parser fixture test (required):** place `November 10, 2026.pdf` in `scraper/tests/fixtures/`. Assert at least:

  | Row | Low | High | Average |
  |---|---|---|---|
  | Tilapia | 120.00 | 200.00 | 158.82 |
  | Bangus, Large | 240.00 | 290.00 | 266.00 |
  | Galunggong, Local | 200.00 | 280.00 | 234.29 |
  | Pork Belly (Liempo), Local | 290.00 | 390.00 | 332.08 |
  | Pork Picnic Shoulder (Kasim), Local | 270.00 | 390.00 | 335.00 |
  | Beef Rump, Local | 365.00 | 480.00 | 438.13 |
  | Beef Brisket, Local | 320.00 | 450.00 | 380.00 |
  | Whole Chicken, Local (4th occurrence) | 190.00 | 230.00 | 214.67 |

  Also assert: report date is 2026-11-10; `Bonito (Frigate Tuna)` is null; `Whole Chicken, Local` yields four distinct ids; no cigarette rows are emitted; 14 sections are detected.
- **Analytics unit tests:** baseline, score, status thresholds, plan multiplier and rounding, budget trimming order, including the "fewer than 14 points" case.
- **Alerts unit tests:** which items trigger, one notification per subscriber per report date, expired subscriptions removed.
- **i18n check:** a test that fails when a key exists in one language file and not the other.
- **Frontend:** component tests for ranking order, filter chips, plan totals, theme switching, and settings merge on sign-in; one Playwright smoke test at 390px, 820px and 1440px widths.

## 13. Milestones

1. **MIMAROPA parser.** Parse the fixture PDF to normalized rows; fixture tests pass.
2. **Drive fetch + backfill.** Confirm public access with the API key, backfill 2026, write `latest.json` and history files. Report how consistent the format is across the year before going further.
3. **Analytics.** Baseline, score, status, plan logic, with tests.
4. **App shell.** Vite + React + router, design tokens, three layouts, region picker, reading real `/data`.
5. **Screens.** Today, Item with chart, Plan, History, Settings.
6. **PWA.** Manifest, service worker, offline notice, install prompt.
7. **NCR parser.** Second region through the same pipeline.
8. **Automation.** GitHub Actions workflow and deploy.
9. **Theme and language.** Dark theme, Filipino translation. (Externalise all strings from milestone 4 onward so this is translation work only.)
10. **Accounts.** Supabase project, sign-in, settings sync.
11. **Price drop alerts.** Subscriptions, sender in the scraper, notification click handling.
12. **Per-market prices (optional).** Investigate the Power BI source (section 4.3), then add "My market" if the data is fresh enough.

Milestones 1–8 give a complete, usable app with no backend. 9–12 are additive; build them in this order.

Stop and ask after milestone 2 if the Drive folders are not publicly readable or if the report format varies in ways this spec does not cover.

## 14. Open questions

- Sign-in methods: this spec assumes email magic link plus Google. Confirm.
- Whether a privacy notice reviewed against the Philippine Data Privacy Act is needed before accounts go live (the app would store email addresses).

- What the four `Whole Chicken, Local` / `Chicken Breast, Local` rows represent (the report drops the distinguishing column). Until known, feature only the consistently priced occurrence and label it plainly.
- Whether MIMAROPA files exist for every day back to January, and whether the layout changed during the year.
- The exact NCR report layout (verify against a downloaded file).
- The 2026 root folder ID (verify; one character may have been misread).
- Final app name.

## 15. Language

- Supported: English (`en`) and Filipino (`fil`).
- Default: `fil` when the browser language starts with `fil` or `tl`, otherwise `en`. The Language setting overrides it.
- Every user-facing string lives in `app/src/locales/{en,fil}.json`, including chips ("8% below usual"), advice labels, empty states, the install sheet and notification text. No literals in components.
- Commodity names come from the catalog and are not translated. Category names (Fish, Pork, Chicken, Beef) are.
- Numbers, currency and dates are formatted with `Intl` for the active language; the peso sign and two-decimal prices stay the same in both.
- The Filipino strings should be written in plain, everyday market Tagalog, not formal translation. Have a native speaker review them before release; mark the file as unreviewed until then.
- Set `<html lang>` to the active language.

## 16. Price drop alerts

Off by default. Turning the setting on triggers the browser permission prompt; if permission is denied, switch the setting back off and explain how to allow it.

- **Platform limits:** on iPhone and iPad, web push works only after the app is added to the home screen (iOS 16.4 or later). When alerts are switched on in an iOS browser tab, show the add-to-home-screen instructions instead of the permission prompt. Hide the setting where `PushManager` is unavailable.
- **Subscription storage:** table `push_subscriptions (id, endpoint unique, p256dh, auth, region, tracked_ids text[], language, user_id nullable, created_at, last_ok_at)`. No account is required; a subscription belongs to a device. Inserts and deletes from the browser go through an RLS policy or a small edge function that only allows a client to manage the row matching its own endpoint. Update the row when region, tracked goods or language change.
- **When to send:** after the scraper writes a new report date for a region, for each subscription in that region, collect tracked items whose status is `buy` today and was not `buy` on the previous report date, plus tracked items at their lowest price in 90 days. If there is at least one, send a single notification. Never more than one per subscriber per report date, and none when the list is empty.
- **Content:** title "Good buys today"; body lists up to three items with their percentages ("Tilapia 8% below usual, Pork kasim 4% below usual"), then "and 2 more" if needed. Localised using the subscription's language.
- **Click:** opens the app on Today.
- **Service worker:** add `push` and `notificationclick` handlers. With `vite-plugin-pwa` this means the `injectManifest` strategy with a custom service worker file.
- **Hygiene:** delete subscriptions that return 404 or 410. Generate the VAPID key pair once; public key in the app config, private key as a secret.

## 17. Accounts

Optional. Everything works signed out; an account only keeps settings in sync across devices and restores them after browser data is cleared.

- **Provider:** Supabase Auth with email magic link and Google sign-in. No passwords.
- **Data:** table `user_settings (user_id primary key references auth.users, settings jsonb, updated_at)`. Row-level security: a user can read and write only their own row.
- **Local-first sync:** `localStorage` stays the source the UI reads from.
  - On sign-in: if a remote row exists and the local settings are still defaults, take remote. If both have been changed, keep whichever has the newer `updatedAt` and tell the user which was kept. If no remote row exists, upload local.
  - While signed in: write through to Supabase on each change (debounced), and pull on app start and on window focus. Last write wins by `updatedAt`.
  - Offline: changes queue locally and sync when back online.
  - On sign-out: keep the local settings on the device.
- **Account screen:** shows the email, "Sign out", and "Delete account", which removes the settings row, any push subscriptions tied to the user, and the auth user.
- **Privacy:** store only the email and the settings object. Add a short privacy notice page linked from the sign-in screen stating what is stored and how to delete it.
- **Config:** Supabase URL and anon key via Vite env variables. Only the anon key ships to the browser.
