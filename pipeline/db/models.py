"""
Typed row contracts for every table the pipeline writes to.

Before this module, each writer built its own positional tuple inline against a
hand-written ``INSERT``. Nothing checked that the tuple matched the column list,
that NOT NULL columns were populated, or that a JSONB column got JSON rather
than a Python dict. Column drift showed up in production as a psycopg2 error at
2am rather than at the call site.

Each record type here owns:

- the fields that map to real columns (verified against ``migrations/``),
- ``validate()``, which fails loudly and specifically *before* SQL is issued,
- normalization of the awkward types (JSONB payloads, text lists, clamped
  floats) so repositories can stay dumb about it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .errors import IntegrityError

# ``content.slug`` is VARCHAR(255); ``companies.ticker`` is VARCHAR(10).
SLUG_MAX_LENGTH = 255
TICKER_MAX_LENGTH = 10

VALID_FILING_STATUSES = {'pending', 'processing', 'analyzed', 'generated', 'published', 'failed'}
VALID_FILING_TYPES = {'10-K', '10-Q'}


class ValidationError(IntegrityError):
    """Record failed validation before reaching the database."""


def _require(value: Any, field_name: str, record: str) -> Any:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValidationError(f"{record}.{field_name} is required but was empty")
    return value


def _truncate(value: Optional[str], limit: int) -> Optional[str]:
    if value is None:
        return None
    return value if len(value) <= limit else value[:limit]


def as_jsonb(value: Any) -> Optional[str]:
    """
    Serialize a Python value for a JSONB column.

    psycopg2 adapts a bare ``dict`` to a Postgres record type, not JSONB, so
    every JSONB write must go through ``json.dumps``. ``default=str`` keeps
    datetimes and Decimals from blowing up a write at the very end of an
    expensive analysis run.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, default=str)


@dataclass
class FilingRecord:
    """A row for ``filings``. Deduplicated on ``accession_number``."""

    company_id: str
    filing_type: str
    accession_number: str
    filing_date: date
    edgar_url: str
    raw_document_url: Optional[str] = None
    fiscal_year: Optional[int] = None
    fiscal_quarter: Optional[int] = None
    period_end_date: Optional[date] = None
    status: str = 'pending'

    def validate(self) -> 'FilingRecord':
        _require(self.company_id, 'company_id', 'FilingRecord')
        _require(self.accession_number, 'accession_number', 'FilingRecord')
        _require(self.filing_date, 'filing_date', 'FilingRecord')
        _require(self.edgar_url, 'edgar_url', 'FilingRecord')

        if self.filing_type not in VALID_FILING_TYPES:
            raise ValidationError(
                f"FilingRecord.filing_type {self.filing_type!r} not in {sorted(VALID_FILING_TYPES)}"
            )
        if self.status not in VALID_FILING_STATUSES:
            raise ValidationError(
                f"FilingRecord.status {self.status!r} not in {sorted(VALID_FILING_STATUSES)}"
            )
        if self.fiscal_quarter is not None and self.fiscal_quarter not in (1, 2, 3, 4):
            raise ValidationError(
                f"FilingRecord.fiscal_quarter must be 1-4 or None, got {self.fiscal_quarter!r}"
            )
        if self.filing_type == '10-Q' and self.fiscal_quarter is None:
            raise ValidationError("FilingRecord: a 10-Q requires a fiscal_quarter")
        return self


@dataclass
class ContentRecord:
    """
    A row for ``content`` — the output of the analyze phase.

    ``executive_summary`` and ``key_takeaways`` are NOT NULL in the schema, so
    ``validate()`` enforces them here rather than letting the insert fail after
    a paid Bedrock call has already been spent.
    """

    filing_id: str
    company_id: str
    slug: str
    executive_summary: str
    key_takeaways: Dict[str, Any] = field(default_factory=dict)
    deep_dive_opportunities: Optional[str] = None
    deep_dive_risks: Optional[str] = None
    deep_dive_strategy: Optional[str] = None
    implications: Optional[str] = None
    meta_description: Optional[str] = None

    def validate(self) -> 'ContentRecord':
        _require(self.filing_id, 'filing_id', 'ContentRecord')
        _require(self.company_id, 'company_id', 'ContentRecord')
        _require(self.slug, 'slug', 'ContentRecord')
        _require(self.executive_summary, 'executive_summary', 'ContentRecord')

        if not isinstance(self.key_takeaways, dict):
            raise ValidationError(
                f"ContentRecord.key_takeaways must be a dict, got {type(self.key_takeaways).__name__}"
            )
        if not self.key_takeaways:
            raise ValidationError("ContentRecord.key_takeaways is NOT NULL and must not be empty")

        self.slug = _truncate(self.slug, SLUG_MAX_LENGTH)
        return self


@dataclass
class MarketDataRecord:
    """A row for ``company_market_data``. Deduplicated on (company_id, data_date)."""

    company_id: str
    ticker: str
    data_date: date
    price: Optional[float] = None
    market_cap: Optional[int] = None
    volume: Optional[int] = None
    change_percent: Optional[float] = None
    source: str = 'finnhub'

    def validate(self) -> 'MarketDataRecord':
        _require(self.company_id, 'company_id', 'MarketDataRecord')
        _require(self.ticker, 'ticker', 'MarketDataRecord')
        _require(self.data_date, 'data_date', 'MarketDataRecord')
        self.ticker = _truncate(self.ticker.upper(), TICKER_MAX_LENGTH)
        return self


@dataclass
class EarningsRecord:
    """
    A row for ``scheduled_earnings``.

    ``fiscal_year`` is NOT NULL in the schema but Finnhub omits it on some
    events, which used to surface as a NOT NULL violation mid-batch.
    """

    company_id: str
    ticker: str
    earnings_date: date
    fiscal_year: int
    fiscal_quarter: Optional[int] = None
    earnings_time: Optional[str] = None
    eps_estimate: Optional[float] = None
    revenue_estimate: Optional[int] = None
    status: str = 'scheduled'
    source: str = 'finnhub'

    def validate(self) -> 'EarningsRecord':
        _require(self.company_id, 'company_id', 'EarningsRecord')
        _require(self.ticker, 'ticker', 'EarningsRecord')
        _require(self.earnings_date, 'earnings_date', 'EarningsRecord')
        if self.fiscal_year is None:
            raise ValidationError("EarningsRecord.fiscal_year is NOT NULL and was not supplied")
        if self.fiscal_quarter is not None and self.fiscal_quarter not in (1, 2, 3, 4):
            raise ValidationError(
                f"EarningsRecord.fiscal_quarter must be 1-4 or None, got {self.fiscal_quarter!r}"
            )
        self.ticker = _truncate(self.ticker.upper(), TICKER_MAX_LENGTH)
        return self


@dataclass
class DeliveryRecord:
    """A row for ``email_deliveries``."""

    content_id: str
    subscriber_id: Optional[str] = None
    status: str = 'sent'
    sent_at: Optional[datetime] = None
    resend_email_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def validate(self) -> 'DeliveryRecord':
        _require(self.content_id, 'content_id', 'DeliveryRecord')
        _require(self.status, 'status', 'DeliveryRecord')
        return self


@dataclass
class ProcessingLogRecord:
    """A row for ``processing_logs``."""

    step: str
    level: str
    message: str
    filing_id: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def validate(self) -> 'ProcessingLogRecord':
        _require(self.step, 'step', 'ProcessingLogRecord')
        _require(self.level, 'level', 'ProcessingLogRecord')
        return self


@dataclass
class UpsertResult:
    """
    Outcome of an idempotent write.

    ``created`` distinguishes an insert from an update, which the batch phases
    report on: "12 new, 3 refreshed" is actionable, "15 saved" is not.
    """

    id: str
    created: bool


def build_slug(
    ticker: str,
    filing_type: str,
    fiscal_year: Optional[int],
    fiscal_quarter: Optional[int],
) -> str:
    """
    Canonical content slug: ``{ticker}/{year}/{period}/{filing_type}``.

    Single source of truth — the analyzer, the backfill scripts and the Next.js
    routes all derive URLs from this shape, so it lives with the row contract
    rather than as a private method on one analyzer.
    """
    ticker_part = (ticker or 'unknown').strip().lower()
    type_part = (filing_type or 'filing').strip().lower()
    year_part = str(fiscal_year) if fiscal_year else 'unknown'

    if type_part == '10-k':
        period = 'fy'
    elif type_part == '10-q' and fiscal_quarter:
        period = f'q{fiscal_quarter}'
    else:
        period = 'other'

    return f"{ticker_part}/{year_part}/{period}/{type_part}"
