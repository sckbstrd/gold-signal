# Gold Signal — Architecture

Status: **DRAFT FOR REVIEW**

Gold Signal is a decision-support tool. It never places trades.
Every screen footer reads: *"Gold Signal is an analytical tool, not financial advice."*

---

## 1. System overview

```
┌──────────────────────── DATA SOURCES ─────────────────────────┐
│ US Treasury (real & nominal curves)  FRED (rates, VIX, Fed)   │
│ Gold/DXY price provider (key)        Frankfurter/ECB, TCMB    │
│ Econ calendar provider (key) / CSV   SPDR GLD, iShares IAU    │
│ WGC central-bank CSV                  [Mock provider: default]│
└───────────────┬───────────────────────────────────────────────┘
                │  Provider adapters (one class per source, behind Protocols)
                ▼
┌──────────────────────── BACKEND (Python / FastAPI) ───────────┐
│ Scheduler (APScheduler worker)                                │
│   └─ Ingestion jobs ─▶ Normalizer ─▶ Validator ─▶ PostgreSQL  │
│                                  (quarantine bad rows)        │
│ As-of Snapshot Builder  (available_at ≤ t, point-in-time)     │
│   └─ Signal Engine (pure functions, versioned params)         │
│        ├─ 7 component engines + gram/FX leg                   │
│        ├─ aggregation · hysteresis · regime · confidence      │
│        └─ explanation codes                                   │
│   └─ Alert evaluator ─▶ alerts table (+ FCM in Phase 7b)      │
│ Backtest runner (the SAME engine, walking dates)              │
│ REST API  /api/v1/...   (read-only, typed, OpenAPI)           │
└───────────────┬───────────────────────────────────────────────┘
                │ HTTPS JSON
                ▼
┌──────────────────────── ANDROID (Kotlin / Compose) ───────────┐
│ Retrofit + kotlinx.serialization ─▶ Repository ─▶ Room cache  │
│ ViewModels (StateFlow) ─▶ Compose screens (Material 3)        │
│ WorkManager: periodic sync + alert polling → notifications    │
│ Localization: EN / TR / RU (reason codes rendered on device)  │
└───────────────────────────────────────────────────────────────┘
```

### Key decisions

| Decision | Choice | Why |
|---|---|---|
| Where the model runs | Backend only | One source of truth. The app can't diverge from backtests. API keys never ship in the APK. |
| Engine purity | `engine/` has no I/O, clock or DB | Deterministic and unit-testable. Live and backtest share one code path. |
| Look-ahead protection | `available_at` on every row; the snapshot builder filters by it | Enforced structurally, not by convention. |
| Provider swap | `Protocol` per data kind, chosen via env var | A new provider is one adapter class. The engine and app don't change. |
| Default provider | `mock` (deterministic synthetic history) | The whole stack runs with zero API keys. |
| Explanations | Structured reason codes plus params | Same output localized to EN/TR/RU on the device. Text is never generic. |
| Alerts (MVP) | WorkManager polls `/alerts?since=` every 30 min | No Firebase setup needed. FCM push added in Phase 7b. |
| Charts | Custom Compose `Canvas` line/bar | Small, no chart-library lock-in. "Do not overload the UI." |
| DI | Hilt | Standard, testable. |
| HTTP | Retrofit + kotlinx.serialization | Mature. The DTOs double as the contract. |

---

## 2. Monorepo folder structure

```
gold-signal/
├── README.md
├── docs/
│   ├── 01_ARCHITECTURE.md          ← this file
│   ├── 02_SCORING_MODEL_V1.md      ← exact formulas
│   ├── 03_DATA_MODEL.md            ← PostgreSQL DDL + domain models
│   ├── 04_API.md                   ← REST contracts + JSON examples
│   └── scoring_v1_reference.py     ← executable spec of the formulas
│
├── backend/
│   ├── pyproject.toml              (fastapi, uvicorn, sqlalchemy 2, alembic, psycopg, pydantic-settings,
│   │                                httpx, apscheduler, pytest, hypothesis)
│   ├── .env.example                (all keys optional; PROVIDER_*=mock by default)
│   ├── Dockerfile
│   ├── docker-compose.yml          (postgres:16, api, worker)
│   ├── alembic/                    (migrations)
│   ├── app/
│   │   ├── main.py                 FastAPI app factory, routers, problem+json errors
│   │   ├── config.py               Settings (env), provider selection, schedule times
│   │   ├── api/v1/
│   │   │   ├── gold.py             /gold/current, /gold/signal, /gold/indicators[/{code}], /gold/history
│   │   │   ├── events.py           /economic-events
│   │   │   ├── fed.py              /fed-expectations
│   │   │   ├── backtest.py         /backtest
│   │   │   ├── alerts.py           /alerts
│   │   │   └── meta.py             /meta/model, /health, /health/data
│   │   ├── schemas/                Pydantic response models (= API contract)
│   │   ├── db/
│   │   │   ├── models.py           SQLAlchemy ORM (mirrors 03_DATA_MODEL.md)
│   │   │   ├── session.py
│   │   │   └── asof.py             point-in-time queries: latest(series, t), window(series, t, days)
│   │   ├── providers/
│   │   │   ├── base.py             Protocols: RatesProvider, PriceProvider, FxProvider, EconCalendarProvider,
│   │   │   │                       EtfHoldingsProvider, CentralBankProvider, FedExpectationsProvider
│   │   │   ├── mock.py             deterministic synthetic data (seeded), full 2005–today history
│   │   │   ├── treasury.py         US Treasury daily par & real yield curves (no key)
│   │   │   ├── fred.py             FRED (free key): DFII10, DGS10, DGS3MO, DGS6MO, DGS1, DFEDTARU/L, EFFR, VIXCLS
│   │   │   ├── frankfurter.py      ECB reference USD/TRY (no key)
│   │   │   ├── tcmb_evds.py        TCMB policy rate & USD/TRY (key)
│   │   │   ├── twelvedata.py       XAU/USD, DXY (key)
│   │   │   ├── spdr_gld.py         GLD daily holdings CSV (no key)
│   │   │   ├── ishares_iau.py      IAU holdings (no key)
│   │   │   ├── fmp_calendar.py     economic calendar incl. consensus (key)
│   │   │   └── csv_import.py       manual CSV import (WGC central banks, consensus backfill)
│   │   ├── ingestion/
│   │   │   ├── jobs.py             one job per series family: fetch → normalize → validate → upsert
│   │   │   └── normalize.py        units (%→bp, oz→t), timezones → UTC, available_at assignment
│   │   ├── validation/
│   │   │   ├── rules.py            range, spike, staleness, timestamp, cross-source checks
│   │   │   └── calendars.py        US (NYSE/SIFMA) and TARGET holiday calendars, business-day age
│   │   ├── engine/                 PURE — no imports from db/, providers/, api/
│   │   │   ├── params/v1_0_0.json  frozen parameters (sha256 stored in model_versions)
│   │   │   ├── primitives.py       soft, sq, trend, freshness, horizon_change
│   │   │   ├── snapshot.py         MarketSnapshot dataclass (engine input)
│   │   │   ├── components/         real_yield.py fed.py dxy.py nominal.py econ.py etf.py central_banks.py
│   │   │   ├── aggregate.py        points, score, bands
│   │   │   ├── hysteresis.py       state machine (signal and regime)
│   │   │   ├── confidence.py
│   │   │   ├── regime.py
│   │   │   ├── gram.py             gram gold price, carry-adjusted FX leg, gram score
│   │   │   ├── explain.py          reason codes
│   │   │   └── evaluate.py         evaluate(snapshot, prev_state, params) -> SignalResult
│   │   ├── backtest/
│   │   │   ├── runner.py           walk trading days, snapshot as-of, engine, positions
│   │   │   └── metrics.py          CAGR, MDD, trades, win rate, …
│   │   ├── alerts/rules.py         alert generation and dedupe
│   │   └── worker.py               scheduler entrypoint
│   └── tests/
│       ├── engine/                 golden tests vs scoring_v1_reference.py, property tests (bounds, monotonicity)
│       ├── test_lookahead.py       a future row must never change a past signal
│       ├── test_validation.py
│       └── test_api_contract.py    responses validate against the schemas in 04_API.md
│
└── android/
    ├── settings.gradle.kts · build.gradle.kts · gradle/libs.versions.toml
    └── app/src/
        ├── main/
        │   ├── AndroidManifest.xml
        │   ├── assets/mock/        current.json signal.json indicators.json … (identical to 04_API.md examples)
        │   ├── java/com/goldsignal/
        │   │   ├── GoldSignalApp.kt            @HiltAndroidApp, WorkManager config, notification channels
        │   │   ├── MainActivity.kt             single activity, NavHost
        │   │   ├── core/
        │   │   │   ├── designsystem/           Theme, colors, SignalChip, ScoreGauge, FactorBar, LineChart, Banner
        │   │   │   ├── format/                 locale-aware numbers, %, bp, ₺/$ currency, relative time
        │   │   │   └── i18n/                   ReasonCodeRenderer (codes → localized strings), LanguageManager
        │   │   ├── domain/
        │   │   │   ├── model/                  Signal, Score, Component, Regime, Confidence, Prices, Event, …
        │   │   │   ├── repository/             GoldRepository (interface)
        │   │   │   └── usecase/                ObserveDashboard, GetIndicatorDetail, RunBacktest, …
        │   │   ├── data/
        │   │   │   ├── remote/                 GoldApi (Retrofit), DTOs (@Serializable), mappers
        │   │   │   ├── mock/                   MockGoldDataSource (reads assets/mock)
        │   │   │   ├── local/                  Room: SnapshotEntity, AlertEntity, DAO, Database
        │   │   │   └── repository/             GoldRepositoryImpl (remote|mock → Room → Flow)
        │   │   ├── feature/
        │   │   │   ├── dashboard/              DashboardScreen + ViewModel
        │   │   │   ├── indicator/              IndicatorDetailScreen (+ Fed, Econ, ETF, CB, Gram variants)
        │   │   │   ├── why/                    WhyScreen (global & gram tabs)
        │   │   │   ├── events/                 EconomicEventsScreen
        │   │   │   ├── backtest/               BacktestScreen + ViewModel
        │   │   │   └── settings/               language, alerts, data source, about/disclaimer
        │   │   └── notifications/              SyncWorker, AlertNotifier, channels
        │   └── res/
        │       ├── values/strings.xml          English (default)
        │       ├── values-tr/strings.xml       Türkçe
        │       ├── values-ru/strings.xml       Русский
        │       └── xml/locales_config.xml      per-app language (Android 13+)
        └── test/ androidTest/                  ViewModel tests, renderer tests, Compose UI tests
```

---

## 3. Backend design

### 3.1 Schedule (UTC, fixed year-round; 23:30 UTC is after the US close in both EST and EDT)

| Job | When | Notes |
|---|---|---|
| prices_intraday | every 15 min, 24×5 | XAUUSD, DXY, USDTRY. Display and provisional score only |
| treasury_curves | 22:30 Mon–Fri | real & nominal 10Y (Treasury, FRED fallback) |
| fred_daily | 22:45 Mon–Fri + 14:00 retry | T-bills, Fed target, EFFR, VIX |
| fx_daily | 16:30 | ECB USD/TRY, TCMB rate |
| etf_holdings | 23:00 Mon–Fri | GLD, IAU |
| econ_calendar | every 10 min, 12:00–15:30 on release days; hourly otherwise | captures consensus before release, actual after |
| central_banks | daily 09:00 (CSV drop folder / provider) | monthly data |
| **official_evaluation** | **23:30 Mon–Fri on US trading days** | writes `signals` (`is_official=true`) and runs alerts |
| provisional_evaluation | every 15 min | `is_official=false`, never changes signal state |

### 3.2 Ingestion pipeline (per row)

```
fetch (retry 3x, exp. backoff, timeout 20s, circuit breaker after 5 failures)
 → normalize (units, UTC, available_at = provider publish time or obs_date + documented lag)
 → validate (rules in §5) → OK: upsert · SUSPECT: store is_valid=false + data_quality_issue · REJECT: issue only
 → update data_sources.last_success_at / last_error
```

Revisions never overwrite. A revised value is inserted as `revision+1` with its own `available_at`, and as-of queries pick
the latest revision visible at time t. That keeps backtests point-in-time correct.

### 3.3 Engine contract

```python
def evaluate(snapshot: MarketSnapshot, prev: EngineState, params: ModelParams) -> SignalResult
```

`MarketSnapshot` holds, per series: windows of `(date, value)` already filtered by `available_at ≤ t`, plus ages in
business days, econ releases, and ETF/CB aggregates. `EngineState` holds the hysteresis and regime state from the
previous official evaluation. `SignalResult` contains everything stored in `signals` + `signal_components` and is
returned by the API.

---

## 4. Android design

### 4.1 Navigation

Bottom bar: **Signal** · **Events** · **Backtest** · **Settings**

```
Signal (Dashboard)
 ├─ tap factor row ──────▶ Indicator Detail (/indicator/{code})
 ├─ tap gram card ───────▶ Gram Gold Detail (/indicator/GRAM_TRY)
 └─ "Why?" ──────────────▶ Why (/why?kind=GLOBAL|GRAM_TRY)
Events ──────────────────▶ list by day, with previous / consensus / actual / surprise / impact
Backtest ────────────────▶ form → results (comparison table, equity curve, trades)
Settings ────────────────▶ Language (System/English/Türkçe/Русский) · Alerts per type · Data source (Live/Mock)
                            · About, model version, disclaimer
```

### 4.2 Dashboard layout (top to bottom)

```
┌─────────────────────────────────────────┐
│ GOLD SIGNAL                 ⟳ 23:31 UTC │
│ [DATA DELAYED: ETF holdings 9 days old] │  ← only when status ≠ OK
│ XAU/USD  $4,180.50   +0.6% 1D           │
│ Gram     ₺6,700.15   +0.7% 1D           │
├─────────────────────────────────────────┤
│        ◜ 61 / 100 ◝                     │  score gauge
│            BUY                          │  confirmed signal (color + text)
│   Confidence 68%                        │
│   Model confidence — not probability    │
│   of future return.                     │
│   Regime: GOLD BULL                     │
│   (pending: none / "STRONG BUY 2/3")    │
├─────────────────────────────────────────┤
│ Real Yield      ████████░░  20.0/30  ▲  │  bar centered at neutral
│ Fed Expect.     ██████▌░░░  13.0/20  ▲  │
│ DXY             ██████░░░░   9.4/15  ▲  │
│ 10Y Yield       ████░░░░░░   4.1/10  ▼  │
│ Economic Data   █████▌░░░░   5.7/10  ·  │
│ ETF Flows       █████▌░░░░   5.8/10  ▲  │
│ Central Banks   ██████░░░░   3.2/5   ▲  │
├─────────────────────────────────────────┤
│ GLOBAL GOLD  BUY   │  GRAM GOLD  BUY    │
├─────────────────────────────────────────┤
│              [  Why?  ]                 │
│ Model v1.0.0 · analytical tool, not     │
│ financial advice                        │
└─────────────────────────────────────────┘
```

Signal colors (light/dark aware, always paired with text): STRONG BUY deep green · BUY green · HOLD amber ·
REDUCE orange · SELL red.

### 4.3 Indicator detail (generic, specialized where needed)

Shows the current value; 1D / 7D / 30D changes (bp or %); trend word (FALLING / RISING / FLAT); gold impact (BULLISH /
BEARISH / NEUTRAL); contribution `20.0 / 30 (+5.0)`; a 1-year line chart with 1M/3M/1Y toggles; data age and source.

- **Fed:** two clearly separated cards, "Current Fed policy" (target range, EFFR, last decision) and
  "Market-implied future policy" (3M / 6M / 12M implied, cuts priced in bp, method label "T-bill proxy").
- **10Y:** nominal vs real vs breakeven, shown as a stacked decomposition so the de-duplication is visible.
- **Economic data:** recent releases table with surprise and impact per row.
- **ETF:** holdings in tonnes, 7D/30D/90D flows. **Central banks:** monthly bars, T12 vs 500 t baseline.
- **Gram gold:** spot, USD/TRY, theoretical gram, optional market gram and premium, return decomposition,
  FX leg vs carry.

### 4.4 Offline and staleness

The repository emits a `Flow<Resource<Dashboard>>` backed by Room. The UI always shows the "last updated" time. If the cached
snapshot is older than 26 h, or the API reports `data_status ≠ OK`, a **DATA DELAYED** banner appears. The app
never shows an old signal as if it were current.

### 4.5 Localization (EN / TR / RU)

- All UI strings live in `strings.xml` (EN default), `values-tr`, `values-ru`, with plurals for days and trades.
  Per-app language picker via `AppCompatDelegate.setApplicationLocales` and `locales_config.xml`.
- **Explanations and notifications are not server text.** The API returns reason codes plus numeric params.
  `ReasonCodeRenderer` maps each code to a localized template, for example
  `why_real_yield_falling` → EN "Real yields have fallen %1$s: %2$s over 30 days." /
  TR "Reel faizler son 30 günde %2$s ile %1$s düştü." / RU "Реальные доходности %1$s снизились: %2$s за 30 дней."
- Numbers are formatted with the locale (`₺6.700,15` in TR, `6 700,15 ₺` in RU, `₺6,700.15` in EN). Signal names are
  localized: GÜÇLÜ AL / AL / TUT / AZALT / SAT and СИЛЬНАЯ ПОКУПКА / ПОКУПАТЬ / ДЕРЖАТЬ / СОКРАЩАТЬ / ПРОДАВАТЬ.
  (Final TR/RU wording should be reviewed by a native speaker before release.)

### 4.6 Notifications

`SyncWorker` (WorkManager, 30 min, network constraint) fetches `/alerts?since=<last_id>`, stores them in Room and
posts local notifications through channels: Signal changes · Regime & extreme events · Macro releases & Fed ·
Data quality. Each channel can be toggled in Settings. Example rendering:

```
GOLD SIGNAL CHANGED
HOLD → BUY · Score 56 → 72
Main reason: US 10Y real yield declined sharply.
Supporting: DXY ↓ · Fed easing expectations ↑
```

---

## 5. Data quality

| Check | Rule | Effect |
|---|---|---|
| Staleness | business-day age vs (fresh, hard) per series, on that series' holiday calendar | f decays to 0; component status AGING / STALE |
| Missing | no valid observation | f = 0; status MISSING; if critical: DATA DELAYED, confidence ≤ 40 |
| Range | hard bounds (real −3…6%, nominal 0…15%, DXY 70…130, XAU 200…20,000, USDTRY 1…500, VIX 5…150) | reject |
| Spike | \|1D change\| > 8σ₁D | quarantine (`is_valid=false`) until confirmed by the next observation or a second source |
| Timestamp | obs_date in the future · available_at < obs_date · out-of-order replay | reject + issue |
| Cross-source | primary vs secondary differ > tolerance (gold 0.5%, yields 5 bp) | status DEGRADED, use primary, log issue |
| Holidays | no observation expected on market holidays, so not counted as stale | calendars.py |
| Delayed releases | scheduled + 2 h passed, actual missing | event status DELAYED; Econ f = 0.5 if I ≥ 0.8; warning in "Why" |
| API failure | provider error or timeout | retry, circuit breaker, `data_sources.last_error`, `/health/data` shows it |

Overall `data_status`: **OK** · **DEGRADED** (non-critical issues, f < 1 somewhere) · **DELAYED** (a critical component
at f = 0). This status ships with every signal response.

---

## 6. Data sources (v1 defaults; all swappable)

| Data | Primary | Fallback | Key? |
|---|---|---|---|
| 10Y real & nominal | US Treasury daily curves | FRED DFII10, DGS10 | FRED: free key |
| Fed target, EFFR, T-bills 3M/6M/1Y, VIX | FRED | — | free key |
| Fed expectations (better) | fed-funds futures / OIS vendor | T-bill proxy | paid, optional |
| XAU/USD, DXY | Twelve Data (or similar) | — | key |
| USD/TRY | TCMB EVDS | Frankfurter (ECB) | EVDS: free key |
| TCMB policy rate | TCMB EVDS | config default | free key |
| Econ actual + consensus | FMP economic calendar (or similar) | CSV import | key |
| ETF holdings | SPDR GLD CSV, iShares IAU | WGC monthly | none |
| Central-bank purchases | WGC Goldhub CSV (manual import) | IMF IFS | none |
| Market gram gold | licensed TR quote provider | — | optional |

Until a key is set, each family falls back to `mock`, and `/health/data` labels it **MOCK** so mock data is
never mistaken for live.

---

## 7. Delivery phases

| Phase | Deliverable | Done when |
|---|---|---|
| 1 | Android UI on mock JSON (all screens, EN/TR/RU) | app builds, every screen renders the fixtures, language switch works |
| 2 | Pure signal engine + tests | golden test matches the reference script; property and look-ahead tests pass |
| 3 | Backend: DB, providers (mock + FRED/Treasury/Frankfurter), validation, API | `docker compose up` serves the contract with mock and live data |
| 4 | Android ↔ backend | Data source = Live works; offline cache and DATA DELAYED banner |
| 5 | Historical backfill (2005→) + band-frequency report | coverage report per series |
| 6 | Backtesting | API + screen; results stored with version and hash |
| 7 | Alerts (polling) → 7b FCM push | notifications for all alert types, localized |
| 8 | More providers, cross-source validation, market gram gold | `/health/data` all green with live keys |
