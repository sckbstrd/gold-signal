"""SQLAlchemy models (portable: SQLite for local/CI, PostgreSQL in production).

Simplified from docs/03_DATA_MODEL.md: signal components are stored inside the
signal payload JSON, and revisions are not tracked yet (none of the v1 sources revise).
Every fact row carries observation date, ``available_at`` and ``ingested_at``.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Float, Integer, String, Text, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UtcDateTime(TypeDecorator):
    """Always UTC and timezone-aware in Python, on every backend.

    SQLite silently drops tzinfo, so values are converted to naive UTC before storage
    there; PostgreSQL stores timestamptz. Naive input is rejected (it would be ambiguous).
    """
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetime stored; use timezone-aware UTC")
        value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None) if dialect.name == "sqlite" else value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class Base(DeclarativeBase):
    type_annotation_map = {datetime: UtcDateTime(), dict: JSON, list: JSON}


class DataSource(Base):
    __tablename__ = "data_sources"
    code: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(10))            # API | CSV | MOCK
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    rows_last_run: Mapped[int] = mapped_column(Integer, default=0)


class MarketData(Base):
    __tablename__ = "market_data"
    __table_args__ = (UniqueConstraint("series_code", "observation_date", "source"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    series_code: Mapped[str] = mapped_column(String(40), index=True)
    observation_date: Mapped[date] = mapped_column(Date, index=True)
    value: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40))
    available_at: Mapped[datetime] = mapped_column()
    ingested_at: Mapped[datetime] = mapped_column(default=utcnow)
    quality: Mapped[str] = mapped_column(String(10), default="OK")   # OK | SUSPECT


class EconomicEvent(Base):
    __tablename__ = "economic_events"
    __table_args__ = (UniqueConstraint("event_code", "reference_period"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_code: Mapped[str] = mapped_column(String(30))
    reference_period: Mapped[str] = mapped_column(String(12))
    scheduled_at: Mapped[datetime] = mapped_column()
    released_at: Mapped[datetime | None] = mapped_column(nullable=True)
    previous: Mapped[float | None] = mapped_column(Float, nullable=True)
    consensus: Mapped[float | None] = mapped_column(Float, nullable=True)
    consensus_captured_at: Mapped[datetime | None] = mapped_column(nullable=True)
    actual: Mapped[float | None] = mapped_column(Float, nullable=True)        # first print, never overwritten
    source: Mapped[str] = mapped_column(String(40))


class EtfHolding(Base):
    __tablename__ = "etf_holdings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date, unique=True)
    tonnes: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40))
    available_at: Mapped[datetime] = mapped_column()


class CentralBankPurchase(Base):
    __tablename__ = "central_bank_purchases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_month: Mapped[date] = mapped_column(Date, unique=True)
    net_tonnes: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(40))
    available_at: Mapped[datetime] = mapped_column()


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (UniqueConstraint("model_version", "as_of_date"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_version: Mapped[str] = mapped_column(String(12))
    as_of_date: Mapped[date] = mapped_column(Date, index=True)
    evaluated_at: Mapped[datetime] = mapped_column()
    origin: Mapped[str] = mapped_column(String(10))           # LIVE | BACKFILL
    score: Mapped[float] = mapped_column(Float)
    raw_band: Mapped[str] = mapped_column(String(12))
    signal: Mapped[str] = mapped_column(String(12))
    confidence: Mapped[int] = mapped_column(Integer)
    regime: Mapped[str] = mapped_column(String(12))
    gram_score: Mapped[float] = mapped_column(Float)
    gram_signal: Mapped[str] = mapped_column(String(12))
    data_status: Mapped[str] = mapped_column(String(10))
    inputs_sha256: Mapped[str] = mapped_column(String(64))
    points: Mapped[dict] = mapped_column(default=dict)          # component code -> points
    payload: Mapped[dict | None] = mapped_column(nullable=True)  # full API payload (latest rows only)


class EngineStateRow(Base):
    __tablename__ = "engine_states"
    model_version: Mapped[str] = mapped_column(String(12), primary_key=True)
    as_of_date: Mapped[date] = mapped_column(Date)
    state: Mapped[dict] = mapped_column()


class LatestQuote(Base):
    """Most recent intraday quote per instrument (display only; never a model input)."""
    __tablename__ = "latest_quotes"
    code: Mapped[str] = mapped_column(String(30), primary_key=True)
    value: Mapped[float] = mapped_column(Float)
    observed_at: Mapped[datetime] = mapped_column()
    source: Mapped[str] = mapped_column(String(40))


class Document(Base):
    """Rendered API responses. The REST API and the static site serve the same documents."""
    __tablename__ = "documents"
    path: Mapped[str] = mapped_column(String(120), primary_key=True)   # e.g. "gold/signal"
    body: Mapped[dict] = mapped_column()
    generated_at: Mapped[datetime] = mapped_column(default=utcnow)


class DataQualityIssue(Base):
    __tablename__ = "data_quality_issues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    detected_at: Mapped[datetime] = mapped_column(default=utcnow)
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    series_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    rule: Mapped[str] = mapped_column(String(20))      # RANGE SPIKE TIMESTAMP CROSS_SOURCE API_FAILURE
    severity: Mapped[str] = mapped_column(String(10))  # INFO WARN CRITICAL
    details: Mapped[dict] = mapped_column(default=dict)
