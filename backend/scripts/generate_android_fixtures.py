"""Generate the Android Phase-1 mock fixtures from the REAL engine.

    python scripts/generate_android_fixtures.py

Writes android/app/src/main/assets/mock/*.json. Every number the app shows in
mock mode is produced by app.engine on the documented worked example (illustrative
data), so the UI is built against genuine engine output and the API contract.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app import presenters  # noqa: E402
from app.backtest.metrics import Trade, summarize  # noqa: E402
from app.demo.worked_example import build_snapshot, prior_state  # noqa: E402
from app.engine import calendars, evaluate, hysteresis, load_params  # noqa: E402
from app.engine.result import SignalState  # noqa: E402

OUT = BACKEND.parent / "android" / "app" / "src" / "main" / "assets" / "mock"
SOURCE = "mock"
NEXT_OFFICIAL = "2026-10-05T23:30:00+00:00"


def write(name: str, data) -> None:
    path = OUT / name
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  {path.relative_to(BACKEND.parent)}  ({path.stat().st_size:,} bytes)")


def demo_backtest(params) -> dict:
    """Synthetic market + real hysteresis + real metrics. Clearly flagged as a demo."""
    start, end, capital, cost_bps = date(2021, 10, 1), date(2026, 9, 30), 10_000.0, 10.0
    days = calendars.business_days(start, end, calendars.NYSE)
    price, score_prev = 1750.0, 50.0
    prices, scores = [], []
    for i, _ in enumerate(days):
        # Price and score cycles are deliberately unrelated (no built-in foresight).
        cyc = math.sin(i / 83 + 0.2) + 0.7 * math.sin(i / 29 + 2.1)
        price *= 1 + 0.00035 + 0.009 * math.sin(i * 1.7 + 0.4) * math.cos(i / 7) + 0.0016 * cyc
        target = 50 + 22 * math.sin(i / 61 + 4.0) + 10 * math.sin(i / 17 + 0.7)
        score_prev = round(0.8 * score_prev + 0.2 * target, 1)
        prices.append(price)
        scores.append(score_prev)

    state, position, cash_rate = SignalState(), 0, 0.03 / 252
    equity, bench, trades, invested = [capital], [capital], [], 0
    open_trade = None
    for i in range(1, len(days)):
        r = prices[i] / prices[i - 1] - 1
        value = equity[-1] * (1 + (r if position else cash_rate))
        signal_yesterday = state.signal
        state = hysteresis.step(state, scores[i - 1], days[i - 1], params)  # signal at t-1 close
        want = 1 if state.signal in ("BUY", "STRONG_BUY") else 0 if state.signal in ("REDUCE", "SELL") else position
        if want != position:                                                  # trade at t close
            value *= 1 - cost_bps / 10_000
            if want:
                open_trade = (days[i], prices[i], state.signal, value)
            else:
                d0, p0, sig0, v0 = open_trade
                trades.append(Trade(d0, round(p0, 2), days[i], round(prices[i], 2),
                                    round(100 * (value / v0 - 1), 2), sig0, state.signal))
                open_trade = None
            position = want
        invested += position
        equity.append(value)
        bench.append(bench[-1] * (1 + r))
        _ = signal_yesterday
    if open_trade:
        d0, p0, sig0, v0 = open_trade
        trades.append(Trade(d0, round(p0, 2), None, round(prices[-1], 2),
                            round(100 * (equity[-1] / v0 - 1), 2), sig0, None))

    curve = [[d.isoformat(), round(e, 2), round(b, 2)]
             for k, (d, e, b) in enumerate(zip(days, equity, bench)) if k % 5 == 0 or k == len(days) - 1]
    return {
        "is_demo": True,
        "model_version": params.version, "params_sha256": params.sha256,
        "request": {"start": start.isoformat(), "end": end.isoformat(), "capital": capital, "cost_bps": cost_bps,
                    "mode": "BINARY", "execution": "NEXT_CLOSE", "cash_yield": "FLAT_3PCT_DEMO"},
        "strategy": summarize(days, equity, capital, trades, invested),
        "buy_and_hold": summarize(days, bench, capital),
        "equity_curve": curve,
        "trades_list": [{"entry_date": t.entry_date.isoformat(), "entry_price": t.entry_price,
                         "exit_date": t.exit_date.isoformat() if t.exit_date else None,
                         "exit_price": t.exit_price, "return_pct": t.return_pct, "days": t.days,
                         "entry_signal": t.entry_signal, "exit_signal": t.exit_signal} for t in trades],
        "data_coverage": {},
        "warnings": [{"code": "DEMO_DATA", "params": {}}],
    }


def demo_history(params) -> tuple[dict, dict, dict]:
    """History, report and health from the mock pipeline (in a temporary SQLite DB). The last 21
    rows are aligned with the worked example's assumed prior state so the demo is self-consistent."""
    import tempfile
    from datetime import datetime, timezone

    from app.config import Settings
    from app.db.session import make_engine, make_sessionmaker
    from app.demo.worked_example import SCORE_HISTORY
    from app.engine.aggregate import band_of
    from app.pipeline.documents import history_report
    from app.pipeline.run import latest_documents, run

    with tempfile.TemporaryDirectory() as tmp:
        settings = Settings(database_url=f"sqlite:///{Path(tmp, 'demo.sqlite').as_posix()}", providers="mock",
                            history_start=date(2025, 8, 1), import_dir=Path(tmp))
        engine = make_engine(settings.database_url)
        with make_sessionmaker(engine)() as s:
            run(s, settings, datetime(2026, 10, 2, 23, 45, tzinfo=timezone.utc))
            docs = latest_documents(s)
        engine.dispose()
    hist = docs["gold/history"]
    rows = hist["points"]
    tail = list(SCORE_HISTORY) + [61.2]
    for row, score in zip(rows[-len(tail):], tail):
        row[1], row[3] = score, band_of(score, params)
        row[2] = "BUY" if row[0] >= "2026-09-25" else "HOLD"
        row[5] = "GOLD_BULL" if row[0] >= "2026-09-25" else row[5]
        row[6], row[7] = score, row[2]
        row[9] = []
    return hist, history_report(rows, params), docs["health/data"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    params = load_params()
    snap = build_snapshot()
    result = evaluate(snap, prior_state(), params).result
    print(f"engine v{result.model_version}: score {result.global_.score} {result.global_.signal}, "
          f"confidence {result.global_.confidence}, regime {result.regime}")

    write("signal.json", presenters.signal_response(result, NEXT_OFFICIAL))
    write("current.json", presenters.current_response(snap, result, SOURCE))
    write("indicators.json", presenters.indicators_response(snap, result, SOURCE))
    for code in [*params.weights.keys(), "GRAM_TRY"]:
        write(f"indicator_{code}.json", presenters.indicator_detail(code, snap, result, SOURCE))
    write("economic_events.json", presenters.events_response(snap, result, params))
    write("backtest_demo.json", demo_backtest(params))
    hist, report, health = demo_history(params)
    write("history.json", hist)
    write("history_report.json", report)
    write("health.json", health)


if __name__ == "__main__":
    main()
