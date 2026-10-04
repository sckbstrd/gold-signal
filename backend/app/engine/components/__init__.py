"""Component registry, in display order (matches params['weights'])."""
from . import central_banks, econ, fed, nominal
from .trend_components import dxy, etf, real_yield

ENGINES = {
    "REAL_YIELD": real_yield,
    "FED": fed.score,
    "DXY": dxy,
    "NOMINAL_10Y": nominal.score,
    "ECON": econ.score,
    "ETF": etf,
    "CENTRAL_BANKS": central_banks.score,
}
