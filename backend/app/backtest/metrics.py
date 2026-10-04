"""Backtest performance metrics (section 10). Pure functions over daily equity and trades."""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Trade:
    entry_date: date
    entry_price: float
    exit_date: date | None       # None = still open at the end of the test
    exit_price: float
    return_pct: float            # net of costs
    entry_signal: str
    exit_signal: str | None

    @property
    def days(self) -> int:
        return ((self.exit_date or self.entry_date) - self.entry_date).days


def max_drawdown_pct(equity: list[float]) -> float:
    peak, worst = equity[0], 0.0
    for v in equity:
        peak = max(peak, v)
        worst = min(worst, v / peak - 1)
    return round(100 * worst, 2)


def cagr_pct(start_value: float, end_value: float, start: date, end: date) -> float:
    years = (end - start).days / 365.25
    if years <= 0 or start_value <= 0:
        return 0.0
    return round(100 * ((end_value / start_value) ** (1 / years) - 1), 2)


def sharpe(daily_returns: list[float]) -> float | None:
    if len(daily_returns) < 20:
        return None
    sd = statistics.pstdev(daily_returns)
    if sd == 0:
        return None
    return round(statistics.fmean(daily_returns) / sd * math.sqrt(252), 2)


def summarize(dates: list[date], equity: list[float], capital: float,
              trades: list[Trade] | None = None, invested_days: int | None = None) -> dict:
    rets = [b / a - 1 for a, b in zip(equity, equity[1:])]
    out = {
        "final_value": round(equity[-1], 2),
        "total_return_pct": round(100 * (equity[-1] / capital - 1), 2),
        "cagr_pct": cagr_pct(capital, equity[-1], dates[0], dates[-1]),
        "max_drawdown_pct": max_drawdown_pct(equity),
        "sharpe": sharpe(rets),
    }
    if trades is None:
        return out
    closed = [t for t in trades if t.exit_date is not None]
    wins = [t.return_pct for t in closed if t.return_pct > 0]
    losses = [t.return_pct for t in closed if t.return_pct <= 0]
    out.update({
        "trades": len(trades),
        "closed_trades": len(closed),
        "win_rate_pct": round(100 * len(wins) / len(closed), 1) if closed else None,
        "avg_gain_pct": round(statistics.fmean(wins), 2) if wins else None,
        "avg_loss_pct": round(statistics.fmean(losses), 2) if losses else None,
        "best_trade_pct": round(max(t.return_pct for t in closed), 2) if closed else None,
        "worst_trade_pct": round(min(t.return_pct for t in closed), 2) if closed else None,
        "time_invested_pct": None if invested_days is None else round(100 * invested_days / len(dates), 1),
    })
    return out
