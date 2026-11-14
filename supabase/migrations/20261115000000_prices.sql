-- Price storage: the scraper's permanent copy of its data, so a new server or an emptied volume
-- restores history from here instead of scraping it again.
--
-- The app never reads these tables (it reads the JSON files the scraper writes). Row level
-- security is on with no policies, so only the service role key (scraper) can read or write.

-- ------------------------------------------------------------------ regional price history
-- One row per region, good and day: the regional figure (median across markets).
create table if not exists public.price_points (
  region text not null,
  item_id text not null,
  day date not null,
  p numeric(12, 2),            -- price; null when not reported
  lo numeric(12, 2),           -- cheapest market
  hi numeric(12, 2),           -- dearest market
  n smallint,                  -- markets that reported
  u text,                      -- unit when not kg
  primary key (region, item_id, day)
);
create index if not exists price_points_region_day on public.price_points (region, day);
alter table public.price_points enable row level security;

-- ------------------------------------------------------------------ markets
create table if not exists public.markets (
  region text not null,
  code text not null,
  name text not null,
  lat double precision,
  lng double precision,
  latest date,                 -- newest price date at this market
  items integer not null default 0,
  primary key (region, code)
);
alter table public.markets enable row level security;

-- Each market's newest price per good (overwritten as newer prices arrive).
create table if not exists public.market_prices (
  region text not null,
  market_code text not null,
  item_id text not null,
  day date not null,
  p numeric(12, 2) not null,
  lo numeric(12, 2),
  hi numeric(12, 2),
  primary key (region, market_code, item_id)
);
alter table public.market_prices enable row level security;

-- ------------------------------------------------------------------ AI notes
-- One row per region and report date, so past notes are kept.
create table if not exists public.insights (
  region text not null,
  as_of date not null,
  body jsonb not null,
  generated_at timestamptz not null default now(),
  primary key (region, as_of)
);
alter table public.insights enable row level security;
