"""Provider registry: which adapters run for GS_PROVIDERS=live|mock."""
from __future__ import annotations

from app.config import Settings
from app.providers.econ_sources import ForexFactoryCalendarProvider
from app.providers.imports import CsvImportProvider, MockProvider
from app.providers.market import (FrankfurterProvider, GoldApiProvider, NyFedProvider, TcmbProvider,
                                  TreasuryProvider, YahooProvider)


def build_providers(settings: Settings) -> list:
    if settings.providers == "mock":
        return [MockProvider()]
    return [TreasuryProvider(), NyFedProvider(), YahooProvider(), FrankfurterProvider(), TcmbProvider(),
            GoldApiProvider(), ForexFactoryCalendarProvider(), CsvImportProvider(settings.import_dir)]
