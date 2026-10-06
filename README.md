# Gold Signal

A transparent, rules-based macro signal for gold (global) and Turkish gram gold.
It answers one question: **are current macroeconomic conditions favorable or unfavorable for gold?**
It does not predict prices and never trades.

> Gold Signal is an analytical tool, not financial advice.

**Android app:** [latest release (APK)](https://github.com/sckbstrd/gold-signal/releases/latest) ·
**Live data:** [sckbstrd.github.io/gold-signal](https://sckbstrd.github.io/gold-signal/)

## Status

| Phase | State |
|---|---|
| 1. Android UI (EN / TR / RU) | Done |
| 2. Deterministic signal engine, model v1.0.0 | Done |
| 3. Backend: providers, validation, database, REST API, scheduler | Done |
| 4. App ↔ backend: live data, intraday prices + provisional score, offline cache, Live/Demo switch | Done |
| 5. Historical backfill since 2008 + history screen and report | Done |
| 6. Backtesting | Not started (the backtest screen shows a flagged demo) |
| 7. Alerts / notifications | Not started |
| 8. More data sources | Partly done: ETF holdings (GLD), central banks (IMF), 9 US releases |

## How it runs

```
GitHub Actions (every 30 min Mon–Fri + Sunday evening; official evaluation after 23:30 UTC)
  └─ backend: fetch → validate → store → evaluate (point-in-time) → render documents
       └─ GitHub Pages: /api/v1/*.json  +  /state/* (carried to the next run)
             └─ Android app (Live mode) reads <server>/api/v1/<path>.json, caches for offline use
```

The same backend also runs as a normal server: `python -m app.cli serve --schedule` (FastAPI, SQLite by
default, PostgreSQL via `GS_DATABASE_URL`). The REST API and the static site serve identical documents.

## Data sources (all free, no API keys)

| Model input | Source |
|---|---|
| US 10Y real yield, 10Y nominal, 3M/6M/1Y bills | US Treasury daily yield curves |
| Fed target range, EFFR | New York Fed reference-rates API |
| DXY, VIX, gold daily closes | Yahoo Finance chart API (unofficial; COMEX GC=F for gold) |
| USD/TRY | ECB reference rate (Frankfurter) |
| TCMB policy rate | TCMB one-week repo table |
| Spot gold quote (display only) | gold-api.com |
| US data: consensus, previous, first-print actual (9 releases) | FXStreet economic-calendar API (history since 2007; consensus captured live before each release going forward) |
| US data actuals, cross-check | BLS public API (CPI y/y, core CPI m/m, payrolls, unemployment) |
| Gold ETF holdings | SPDR Gold Shares (GLD) daily tonnes since 2004 — the largest gold ETF, used as the proxy for all gold ETFs |
| Central-bank purchases | IMF International Liquidity: monthly official gold holdings of all reporting countries since 2004 (**reported** purchases only — unreported buying estimated by the World Gold Council is not included) |
| Any of the above | Optional CSV override (`backend/app/providers/imports.py`) |

Missing inputs are never hidden. They count as neutral, lower model confidence, and appear as data warnings.

## Findings from the 2008–2026 reconstruction (descriptive, not used for tuning)

- The confirmed signal was HOLD on ~94% of days. BUY ~3%, REDUCE ~3%, SELL 0.1%, and STRONG BUY never.
  Scores sit between 42 and 57 on 80% of days.
- The first reconstruction (2026-10-04) had no ETF, central-bank or economic data, so 25 of the 100 points
  were always neutral. On 2026-10-07 those sources were added (see the table above) and the history was
  rebuilt from scratch with the same frozen model; the report at `/api/v1/gold/history/report` is the
  current one.
- The direction is sensible. 2022 (Fed hiking) was REDUCE/SELL 42% of the time; 2024 was BUY 17.5%.
- Model v1.0.0 is frozen. Any recalibration must be a new model version (v1.1) and an explicit decision.

## Develop

```bash
cd backend && pip install -r requirements.txt && python -m pytest -q
GS_PROVIDERS=mock python -m app.cli run --now 2026-10-02T23:45:00+00:00 --history-start 2025-08-01
python -m app.cli run --export site          # live data, full backfill on first run (~4 min)
python -m scripts.generate_android_fixtures  # refresh the app's demo fixtures from the engine
```

```bash
cd android
./gradlew :app:assembleDebug :app:testDebugUnitTest
./gradlew :app:recordRoborazziDebug          # renders every screen to app/build/outputs/roborazzi
```

**Windows note:** keep the project at a short path. Deep paths exceed the 260-character limit and break the
Android build tools and some Python packages.

| Doc | Contents |
|---|---|
| [docs/01_ARCHITECTURE.md](docs/01_ARCHITECTURE.md) | System design, folders, screens, data quality, i18n, phases |
| [docs/02_SCORING_MODEL_V1.md](docs/02_SCORING_MODEL_V1.md) | Exact formulas and the worked example |
| [docs/03_DATA_MODEL.md](docs/03_DATA_MODEL.md) | Data model |
| [docs/04_API.md](docs/04_API.md) | REST contracts with example JSON |
| [docs/screenshots/](docs/screenshots) | Rendered screens (EN / TR / RU, light and dark) |
