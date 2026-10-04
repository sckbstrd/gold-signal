"""Pure trend components.

2.1 Real Yield (US 10Y TIPS, bp)     falling real yields are bullish
2.3 DXY (log %)                      a falling dollar is bullish
2.6 Gold ETF holdings (log %)        inflows are bullish; 7D/30D/90D only, so slow by construction
"""
from __future__ import annotations

from ..params import ModelParams
from ..result import RawComponent
from ..snapshot import MarketSnapshot
from .common import trend_component


def real_yield(snap: MarketSnapshot, params: ModelParams) -> RawComponent:
    return trend_component(snap.real_10y, "bp", params.component("REAL_YIELD"), params,
                           snap.as_of_date, "REAL_YIELD")


def dxy(snap: MarketSnapshot, params: ModelParams) -> RawComponent:
    return trend_component(snap.dxy, "logpct", params.component("DXY"), params, snap.as_of_date, "DXY")


def etf(snap: MarketSnapshot, params: ModelParams) -> RawComponent:
    return trend_component(snap.etf_holdings, "logpct", params.component("ETF"), params,
                           snap.as_of_date, "ETF")
