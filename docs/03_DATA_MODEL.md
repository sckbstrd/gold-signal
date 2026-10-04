# Gold Signal — Data Model (PostgreSQL 16)

Status: **DRAFT FOR REVIEW**

Conventions:
- Every timestamp is `timestamptz`, stored in UTC.
- Every fact row has three times:
  - `observation_date`: what the value is about
  - `available_at`: when the public could know it; the look-ahead key
  - `ingested_at`: when we stored it
- Raw provider payloads are kept in `raw` (jsonb) next to normalized values.
- Revisions are appended, never overwritten.

```sql
-- ───────────────────────────── reference ─────────────────────────────
CREATE TYPE source_kind      AS ENUM ('MOCK','API','CSV','MANUAL');
CREATE TYPE quality_status   AS ENUM ('OK','SUSPECT','REJECTED');
CREATE TYPE event_status     AS ENUM ('SCHEDULED','RELEASED','DELAYED','CANCELLED');
CREATE TYPE signal_kind      AS ENUM ('GLOBAL','GRAM_TRY');
CREATE TYPE signal_label     AS ENUM ('STRONG_BUY','BUY','HOLD','REDUCE','SELL');
CREATE TYPE regime_label     AS ENUM ('GOLD_BULL','GOLD_BEAR','TRANSITION','PANIC');
CREATE TYPE data_status      AS ENUM ('OK','DEGRADED','DELAYED');
CREATE TYPE fed_method       AS ENUM ('TBILL_PROXY','FED_FUNDS_FUTURES','OIS');

CREATE TABLE data_sources (
  id              smallserial PRIMARY KEY,
  code            text UNIQUE NOT NULL,          -- 'fred', 'treasury', 'twelvedata', 'mock', ...
  name            text NOT NULL,
  kind            source_kind NOT NULL,
  base_url        text,
  requires_key    boolean NOT NULL DEFAULT false,
  enabled         boolean NOT NULL DEFAULT true,
  last_success_at timestamptz,
  last_error_at   timestamptz,
  last_error      text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

-- Catalog of time series (one row per logical series, independent of provider)
CREATE TABLE series (
  code            text PRIMARY KEY,   -- US_REAL_10Y, US_NOM_10Y, DXY, XAUUSD, USDTRY, VIX,
                                      -- US_TBILL_3M, US_TBILL_6M, US_TBILL_1Y, FED_TARGET_LOWER,
                                      -- FED_TARGET_UPPER, EFFR, TCMB_POLICY_RATE, GRAM_GOLD_MARKET
  name            text NOT NULL,
  unit            text NOT NULL,      -- 'pct', 'index', 'usd_per_oz', 'try_per_usd', 'try_per_gram'
  frequency       text NOT NULL,      -- 'daily','intraday','monthly'
  calendar        text NOT NULL,      -- 'US', 'TARGET', 'TR', 'FX24x5'
  primary_source  smallint REFERENCES data_sources(id),
  fallback_source smallint REFERENCES data_sources(id),
  publication_lag interval NOT NULL,  -- used to derive available_at for historical backfill
  fresh_bdays     smallint NOT NULL,
  hard_bdays      smallint NOT NULL,
  min_value       numeric, max_value numeric,      -- range check
  spike_sigma_1d  numeric,                         -- spike check reference
  critical        boolean NOT NULL DEFAULT false
);

-- ───────────────────────────── market data ───────────────────────────
CREATE TABLE market_data (
  id               bigserial PRIMARY KEY,
  series_code      text NOT NULL REFERENCES series(code),
  observation_date date NOT NULL,
  observed_at      timestamptz NOT NULL,          -- exact quote time (close or intraday tick)
  value            numeric(20,8) NOT NULL,        -- normalized (pct, index, price)
  raw              jsonb,                         -- provider payload fragment
  source_id        smallint NOT NULL REFERENCES data_sources(id),
  revision         smallint NOT NULL DEFAULT 0,
  is_close         boolean NOT NULL DEFAULT true, -- false for intraday ticks
  quality          quality_status NOT NULL DEFAULT 'OK',
  available_at     timestamptz NOT NULL,
  ingested_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (series_code, observation_date, is_close, source_id, revision)
);
CREATE INDEX market_data_asof ON market_data (series_code, available_at DESC, observation_date DESC)
  WHERE quality = 'OK';

-- ───────────────────────────── macro events ──────────────────────────
CREATE TABLE economic_events (
  id               bigserial PRIMARY KEY,
  event_code       text NOT NULL,          -- CPI_YOY, CORE_CPI_MOM, PCE_YOY, CORE_PCE_MOM, NFP,
                                           -- UNEMPLOYMENT, INITIAL_CLAIMS, ISM_MFG, ISM_SERVICES, FOMC_DECISION
  country          char(2) NOT NULL DEFAULT 'US',
  reference_period text NOT NULL,          -- '2026-09', '2026-W39'
  unit             text NOT NULL,          -- 'pct', 'thousands', 'index', 'pct_rate'
  scheduled_at     timestamptz NOT NULL,
  released_at      timestamptz,            -- = available_at of the actual
  status           event_status NOT NULL DEFAULT 'SCHEDULED',
  previous         numeric(14,4),
  consensus        numeric(14,4),
  consensus_captured_at timestamptz,       -- must be < released_at to be used
  actual           numeric(14,4),          -- FIRST PRINT, never overwritten
  actual_revised   numeric(14,4),          -- informational only, never used by the engine
  surprise         numeric(14,4) GENERATED ALWAYS AS (actual - consensus) STORED,
  surprise_z       numeric(10,4),          -- surprise / sigma (model-version specific, also in components)
  importance       numeric(3,2) NOT NULL,
  gold_direction   smallint NOT NULL CHECK (gold_direction IN (-1, 1)),
  source_id        smallint NOT NULL REFERENCES data_sources(id),
  raw              jsonb,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (event_code, reference_period)
);
CREATE INDEX economic_events_release ON economic_events (released_at DESC);

CREATE TABLE fed_expectations (
  id                   bigserial PRIMARY KEY,
  as_of_date           date NOT NULL,
  observed_at          timestamptz NOT NULL,
  method               fed_method NOT NULL,
  current_target_lower numeric(6,3) NOT NULL,
  current_target_upper numeric(6,3) NOT NULL,
  effr                 numeric(6,3),
  implied_3m           numeric(6,3) NOT NULL,
  implied_6m           numeric(6,3) NOT NULL,
  implied_12m          numeric(6,3) NOT NULL,
  next_meeting_date    date,
  p_cut_next           numeric(5,4),       -- only with a futures/OIS provider
  p_hold_next          numeric(5,4),
  p_hike_next          numeric(5,4),
  source_id            smallint NOT NULL REFERENCES data_sources(id),
  raw                  jsonb,
  available_at         timestamptz NOT NULL,
  ingested_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (as_of_date, method, source_id)
);

CREATE TABLE etf_flows (
  id               bigserial PRIMARY KEY,
  etf_ticker       text NOT NULL,          -- 'GLD', 'IAU'
  as_of_date       date NOT NULL,
  holdings_tonnes  numeric(12,4) NOT NULL,
  holdings_oz      numeric(16,2),
  flow_tonnes      numeric(12,4),          -- vs previous observation
  aum_usd          numeric(18,2),
  source_id        smallint NOT NULL REFERENCES data_sources(id),
  raw              jsonb,
  available_at     timestamptz NOT NULL,
  ingested_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (etf_ticker, as_of_date)
);

CREATE TABLE central_bank_purchases (
  id               bigserial PRIMARY KEY,
  period_month     date NOT NULL,          -- first day of the reference month
  country_code     text NOT NULL,          -- ISO code, or 'WORLD' for the aggregate used by the model
  net_tonnes       numeric(10,2) NOT NULL,
  revision         smallint NOT NULL DEFAULT 0,
  source_id        smallint NOT NULL REFERENCES data_sources(id),
  raw              jsonb,
  available_at     timestamptz NOT NULL,   -- publication date (≈ +45–70 days)
  ingested_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (period_month, country_code, revision)
);

-- ───────────────────────────── model & signals ───────────────────────
CREATE TABLE model_versions (
  version          text PRIMARY KEY,       -- '1.0.0'
  params           jsonb NOT NULL,
  params_sha256    char(64) NOT NULL,
  frozen_at        timestamptz,            -- set on approval; immutable afterwards
  notes            text
);

CREATE TABLE signals (
  id               bigserial PRIMARY KEY,
  model_version    text NOT NULL REFERENCES model_versions(version),
  kind             signal_kind NOT NULL,
  evaluated_at     timestamptz NOT NULL,
  as_of_date       date NOT NULL,          -- trading day evaluated
  is_official      boolean NOT NULL,
  score            numeric(5,1) NOT NULL,
  raw_band         signal_label NOT NULL,
  signal           signal_label NOT NULL,  -- confirmed (after hysteresis)
  previous_signal  signal_label,
  pending_signal   signal_label,
  pending_days     smallint NOT NULL DEFAULT 0,
  days_in_band     smallint NOT NULL DEFAULT 0,
  confidence       smallint NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  confidence_parts jsonb NOT NULL,         -- {agreement, magnitude, freshness, persistence}
  regime           regime_label NOT NULL,
  regime_candidate regime_label NOT NULL,
  regime_pending_days smallint NOT NULL DEFAULT 0,
  data_status      data_status NOT NULL,
  explanation      jsonb NOT NULL,         -- reason codes + params (see 04_API.md)
  inputs_sha256    char(64) NOT NULL,      -- hash of the snapshot (reproducibility)
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX signals_official_unique ON signals (model_version, kind, as_of_date) WHERE is_official;
CREATE INDEX signals_latest ON signals (kind, is_official, evaluated_at DESC);

CREATE TABLE signal_components (
  id               bigserial PRIMARY KEY,
  signal_id        bigint NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
  component_code   text NOT NULL,          -- REAL_YIELD, FED, DXY, NOMINAL_10Y, ECON, ETF, CENTRAL_BANKS, FX_USDTRY
  weight           numeric(5,2) NOT NULL,
  inputs           jsonb NOT NULL,         -- raw values and horizon changes used
  sub_scores       jsonb NOT NULL,         -- per-horizon / per-sub-score values
  s_raw            numeric(7,4) NOT NULL,
  freshness        numeric(5,4) NOT NULL,
  s_effective      numeric(7,4) NOT NULL,
  points           numeric(6,2) NOT NULL,
  tilt             numeric(6,2) NOT NULL,
  data_age_bdays   smallint,
  status           text NOT NULL,          -- FRESH | AGING | STALE | MISSING | MOCK
  UNIQUE (signal_id, component_code)
);

CREATE TABLE alerts (
  id               bigserial PRIMARY KEY,
  type             text NOT NULL,          -- SIGNAL_CHANGED, SCORE_MOVE, REGIME_CHANGED, MACRO_RELEASE,
                                           -- FED_DECISION, EXTREME_EVENT, DATA_DELAYED
  kind             signal_kind,
  created_at       timestamptz NOT NULL DEFAULT now(),
  signal_id        bigint REFERENCES signals(id),
  event_id         bigint REFERENCES economic_events(id),
  payload          jsonb NOT NULL,         -- codes + params, localized on device
  dedupe_key       text UNIQUE NOT NULL,   -- e.g. 'SIGNAL_CHANGED:GLOBAL:2026-10-02'
  push             boolean NOT NULL DEFAULT true
);

CREATE TABLE backtest_results (
  id               bigserial PRIMARY KEY,
  model_version    text NOT NULL REFERENCES model_versions(version),
  params_sha256    char(64) NOT NULL,
  request_sha256   char(64) NOT NULL UNIQUE, -- cache key: version+start+end+capital+mode+costs
  start_date       date NOT NULL,
  end_date         date NOT NULL,
  initial_capital  numeric(18,2) NOT NULL,
  mode             text NOT NULL DEFAULT 'BINARY',
  cost_bps         numeric(6,2) NOT NULL,
  strategy_metrics jsonb NOT NULL,
  benchmark_metrics jsonb NOT NULL,
  equity_curve     jsonb NOT NULL,         -- [[date, strategy, benchmark], ...] (weekly-sampled for the API)
  trades           jsonb NOT NULL,
  data_coverage    jsonb NOT NULL,
  warnings         jsonb NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE data_quality_issues (
  id               bigserial PRIMARY KEY,
  detected_at      timestamptz NOT NULL DEFAULT now(),
  source_id        smallint REFERENCES data_sources(id),
  series_code      text,
  rule             text NOT NULL,          -- RANGE, SPIKE, STALE, MISSING, TIMESTAMP, CROSS_SOURCE, API_FAILURE, DELAYED_RELEASE
  severity         text NOT NULL,          -- INFO, WARN, CRITICAL
  details          jsonb NOT NULL,
  resolved_at      timestamptz
);
CREATE INDEX dq_open ON data_quality_issues (resolved_at) WHERE resolved_at IS NULL;
```

## Point-in-time query (the core of look-ahead safety)

```sql
-- latest valid value of :series visible at :t (highest revision visible at t)
SELECT DISTINCT ON (observation_date) observation_date, value
FROM market_data
WHERE series_code = :series AND quality = 'OK' AND is_close
  AND source_id = :source          -- primary; asof.py retries with the fallback source if empty/stale
  AND available_at <= :t
ORDER BY observation_date DESC, revision DESC
LIMIT :n;
```

Every engine input is loaded through `db/asof.py`, which only exposes this pattern. Nothing else can read fact
tables for the engine.

## Android local model (Room)

| Entity | Purpose |
|---|---|
| `SnapshotEntity(kind PK, json, fetchedAt, asOf)` | Last `/gold/signal` + `/gold/current` + `/gold/indicators` responses as JSON (offline display) |
| `IndicatorSeriesEntity(code, range, json, fetchedAt)` | Cached chart series |
| `AlertEntity(id PK, type, createdAt, payloadJson, notified)` | Alert inbox, dedupe for notifications |
| `EventEntity(id PK, json, releasedAt)` | Recent and upcoming economic events |

Domain models on Android mirror the API DTOs (04_API.md) one-to-one, with `enum class` for labels and
`kotlinx.datetime.Instant` for timestamps.
