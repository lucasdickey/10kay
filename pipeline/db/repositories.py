"""
Repositories: the only place the pipeline issues writes.

Every write here is **idempotent**. The pipeline is re-run constantly — backfills
overlap, GitHub Actions retry, workers crash midway — and a plain ``INSERT``
turns each of those into either a duplicate row or a hard constraint failure.
Each method below resolves to ``INSERT ... ON CONFLICT DO UPDATE`` on a real
unique index, and reports whether it inserted or refreshed via ``UpsertResult``.

The natural keys, all backed by unique indexes in ``migrations/``:

    filings              accession_number                      (001)
    content              filing_id WHERE is_current            (010)
    company_market_data  (company_id, data_date)               (009)
    scheduled_earnings   (company_id, fiscal_year, COALESCE(fiscal_quarter, 0))  (010)

``xmax = 0`` in the ``RETURNING`` clause is the standard Postgres trick for
telling an ``ON CONFLICT`` insert from an update: a freshly inserted tuple has no
deleting transaction id.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

import psycopg2
from psycopg2 import errors as pg_errors

from .connection import read_cursor, savepoint, transaction, translate_error
from .errors import DatabaseError, IntegrityError, RecordNotFound
from .models import (
    ContentRecord,
    DeliveryRecord,
    EarningsRecord,
    FilingRecord,
    MarketDataRecord,
    ProcessingLogRecord,
    UpsertResult,
    as_jsonb,
)

log = logging.getLogger(__name__)


class Repository:
    """Base repository. Holds a connection; never opens or closes one."""

    def __init__(self, conn: psycopg2.extensions.connection):
        if conn is None:
            raise DatabaseError(
                f"{type(self).__name__} requires a database connection, got None"
            )
        self.conn = conn


class CompanyRepository(Repository):
    """Reads and writes for ``companies``."""

    def find_id(self, ticker: str) -> Optional[str]:
        with read_cursor(self.conn) as cur:
            cur.execute(
                "SELECT id FROM companies WHERE UPPER(ticker) = UPPER(%s)",
                (ticker,),
            )
            row = cur.fetchone()
        return row['id'] if row else None

    def require_id(self, ticker: str) -> str:
        """Resolve a ticker, or raise ``RecordNotFound`` naming the ticker."""
        company_id = self.find_id(ticker)
        if company_id is None:
            raise RecordNotFound(f"Company {ticker!r} is not in the companies table")
        return company_id

    def list_enabled(self) -> List[Dict[str, Any]]:
        with read_cursor(self.conn) as cur:
            cur.execute(
                """
                SELECT id, ticker, name, sector, exchange, metadata
                FROM companies
                WHERE enabled = true
                ORDER BY ticker
                """
            )
            return [dict(row) for row in cur.fetchall()]

    def upsert(
        self,
        ticker: str,
        name: str,
        *,
        exchange: Optional[str] = None,
        sector: Optional[str] = None,
        enabled: bool = True,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> UpsertResult:
        with transaction(self.conn, dict_rows=True) as cur:
            cur.execute(
                """
                INSERT INTO companies (ticker, name, exchange, sector, enabled, metadata)
                VALUES (UPPER(%s), %s, %s, %s, %s, %s)
                ON CONFLICT (ticker) DO UPDATE SET
                    name     = EXCLUDED.name,
                    exchange = COALESCE(EXCLUDED.exchange, companies.exchange),
                    sector   = COALESCE(EXCLUDED.sector, companies.sector),
                    enabled  = EXCLUDED.enabled,
                    metadata = COALESCE(EXCLUDED.metadata, companies.metadata)
                RETURNING id, (xmax = 0) AS created
                """,
                (ticker, name, exchange, sector, enabled, as_jsonb(metadata)),
            )
            row = cur.fetchone()
        return UpsertResult(id=str(row['id']), created=row['created'])


class FilingRepository(Repository):
    """Reads and writes for ``filings``."""

    #: ``filings`` carries two unique keys, and a write can collide with either:
    #:
    #:   filings_accession_number_key  UNIQUE (accession_number)                     [001]
    #:   idx_filings_unique  UNIQUE (company_id, filing_type, fiscal_year,
    #:                               COALESCE(fiscal_quarter, 0))                    [003]
    #:
    #: The same filing re-fetched collides on the first. An *amended* filing
    #: (10-Q/A, or a re-filed period) has a new accession number for a period
    #: that already exists, so it collides on the second — which a single
    #: ``ON CONFLICT (accession_number)`` cannot catch. Postgres allows only one
    #: conflict target per statement, so the period collision is handled as an
    #: explicit second step.
    _INSERT_SQL = """
        INSERT INTO filings (
            company_id, filing_type, accession_number, filing_date,
            period_end_date, fiscal_year, fiscal_quarter,
            edgar_url, raw_document_url, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (accession_number) DO UPDATE SET
            company_id       = EXCLUDED.company_id,
            filing_date      = EXCLUDED.filing_date,
            period_end_date  = COALESCE(EXCLUDED.period_end_date, filings.period_end_date),
            fiscal_year      = COALESCE(EXCLUDED.fiscal_year, filings.fiscal_year),
            fiscal_quarter   = COALESCE(EXCLUDED.fiscal_quarter, filings.fiscal_quarter),
            edgar_url        = EXCLUDED.edgar_url,
            raw_document_url = COALESCE(EXCLUDED.raw_document_url, filings.raw_document_url),
            updated_at       = NOW()
        RETURNING id, (xmax = 0) AS created
    """

    #: Supersede the row already holding this fiscal period with the amendment.
    _SUPERSEDE_SQL = """
        UPDATE filings SET
            accession_number = %s,
            filing_date      = %s,
            period_end_date  = COALESCE(%s, period_end_date),
            edgar_url        = %s,
            raw_document_url = COALESCE(%s, raw_document_url),
            updated_at       = NOW()
        WHERE company_id = %s
          AND filing_type = %s
          AND fiscal_year = %s
          AND COALESCE(fiscal_quarter, 0) = COALESCE(%s, 0)
        RETURNING id
    """

    def upsert(self, record: FilingRecord) -> UpsertResult:
        """
        Insert or refresh a filing, tolerating both of the table's unique keys.

        Re-fetching a filing stored without an S3 URL backfills that URL rather
        than raising. ``COALESCE(EXCLUDED...)`` means a re-fetch never nulls out
        data we already have, and the status is deliberately *not* reset — a
        filing already analyzed must not return to ``pending`` and be paid for a
        second time.
        """
        record.validate()

        params = (
            record.company_id,
            record.filing_type,
            record.accession_number,
            record.filing_date,
            record.period_end_date,
            record.fiscal_year,
            record.fiscal_quarter,
            record.edgar_url,
            record.raw_document_url,
            record.status,
        )

        with transaction(self.conn, dict_rows=True):
            try:
                with savepoint(self.conn, dict_rows=True) as cur:
                    cur.execute(self._INSERT_SQL, params)
                    row = cur.fetchone()
                return UpsertResult(id=str(row['id']), created=row['created'])

            except IntegrityError as exc:
                if 'idx_filings_unique' not in str(exc):
                    raise
                log.info(
                    "Filing %s supersedes the existing %s %s %s filing for this company",
                    record.accession_number, record.filing_type,
                    record.fiscal_year, record.fiscal_quarter,
                )

            with savepoint(self.conn, dict_rows=True) as cur:
                cur.execute(
                    self._SUPERSEDE_SQL,
                    (
                        record.accession_number,
                        record.filing_date,
                        record.period_end_date,
                        record.edgar_url,
                        record.raw_document_url,
                        record.company_id,
                        record.filing_type,
                        record.fiscal_year,
                        record.fiscal_quarter,
                    ),
                )
                row = cur.fetchone()

            if row is None:
                raise IntegrityError(
                    f"Filing {record.accession_number} collided with "
                    "idx_filings_unique but no row matched the period"
                )
            return UpsertResult(id=str(row['id']), created=False)

    def exists(self, accession_number: str) -> bool:
        with read_cursor(self.conn) as cur:
            cur.execute(
                "SELECT 1 FROM filings WHERE accession_number = %s",
                (accession_number,),
            )
            return cur.fetchone() is not None

    def get_context(self, filing_id: str) -> Dict[str, Any]:
        """
        Everything the analyzer needs about a filing, in one round trip.

        The analyzer previously issued three separate queries for the same row
        (metadata for the prompt, company_id for the insert, period fields for
        the slug), each able to see a different snapshot.
        """
        with read_cursor(self.conn) as cur:
            cur.execute(
                """
                SELECT
                    f.id                AS filing_id,
                    f.company_id,
                    f.filing_type,
                    f.fiscal_year,
                    f.fiscal_quarter,
                    f.filing_date,
                    f.period_end_date,
                    f.accession_number,
                    f.raw_document_url,
                    f.status,
                    c.ticker,
                    c.name              AS company_name,
                    c.sector
                FROM filings f
                JOIN companies c ON f.company_id = c.id
                WHERE f.id = %s
                """,
                (filing_id,),
            )
            row = cur.fetchone()

        if row is None:
            raise RecordNotFound(f"Filing {filing_id} not found")

        context = dict(row)
        quarter = context.get('fiscal_quarter')
        context['fiscal_period'] = f"Q{quarter}" if quarter else 'FY'
        return context

    def set_status(
        self,
        filing_id: str,
        status: str,
        *,
        error_message: Optional[str] = None,
        processed: bool = False,
    ) -> None:
        with transaction(self.conn) as cur:
            cur.execute(
                """
                UPDATE filings
                SET status        = %s,
                    error_message = %s,
                    processed_at  = CASE WHEN %s THEN NOW() ELSE processed_at END,
                    updated_at    = NOW()
                WHERE id = %s
                """,
                (status, error_message, processed, filing_id),
            )

    def pending(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Filings awaiting analysis.

        ``NOT EXISTS (SELECT 1 FROM content ...)`` guards against the case where
        a crash left ``status = 'pending'`` after content was already written —
        without it, a rerun pays Bedrock a second time for the same filing.
        """
        sql = """
            SELECT f.id AS filing_id, f.filing_type, f.fiscal_year, f.fiscal_quarter,
                   c.ticker, c.name AS company_name
            FROM filings f
            JOIN companies c ON f.company_id = c.id
            WHERE f.status = 'pending'
              AND NOT EXISTS (
                  SELECT 1 FROM content ct
                  WHERE ct.filing_id = f.id AND ct.is_current
              )
            ORDER BY f.filing_date DESC NULLS LAST
        """
        params: List[Any] = []
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)

        with read_cursor(self.conn) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def count_pending(self) -> int:
        with read_cursor(self.conn) as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS n
                FROM filings f
                WHERE f.status = 'pending'
                  AND NOT EXISTS (
                      SELECT 1 FROM content ct
                      WHERE ct.filing_id = f.id AND ct.is_current
                  )
                """
            )
            return int(cur.fetchone()['n'])


class ContentRepository(Repository):
    """Reads and writes for ``content``."""

    #: How many times to disambiguate a colliding slug before giving up.
    _SLUG_ATTEMPTS = 4

    def upsert_analysis(self, record: ContentRecord) -> UpsertResult:
        """
        Write an analysis, keyed on ``filing_id`` among current rows.

        Two conflicts are possible and both used to abort the write:

        1. Content already exists for this filing (a re-analysis). Handled by
           ``ON CONFLICT (filing_id) WHERE is_current DO UPDATE``.
        2. A *different* filing already owns the slug — an amended 10-Q for the
           same quarter derives an identical slug, and ``content.slug`` is
           UNIQUE. Handled by retrying with a suffix taken from the filing id.

        The whole thing runs in one transaction, so a failure leaves neither a
        half-written content row nor a filing wrongly marked ``analyzed``.
        """
        record.validate()
        base_slug = record.slug

        with transaction(self.conn, dict_rows=True):
            for attempt in range(self._SLUG_ATTEMPTS):
                slug = base_slug if attempt == 0 else self._disambiguate(
                    base_slug, record.filing_id, attempt
                )
                try:
                    with savepoint(self.conn, dict_rows=True) as cur:
                        cur.execute(
                            """
                            INSERT INTO content (
                                filing_id, company_id, slug,
                                executive_summary, key_takeaways,
                                deep_dive_opportunities, deep_dive_risks,
                                deep_dive_strategy, implications,
                                meta_description, version, is_current
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, true)
                            ON CONFLICT (filing_id) WHERE is_current DO UPDATE SET
                                company_id              = EXCLUDED.company_id,
                                slug                    = EXCLUDED.slug,
                                executive_summary       = EXCLUDED.executive_summary,
                                key_takeaways           = EXCLUDED.key_takeaways,
                                deep_dive_opportunities = EXCLUDED.deep_dive_opportunities,
                                deep_dive_risks         = EXCLUDED.deep_dive_risks,
                                deep_dive_strategy      = EXCLUDED.deep_dive_strategy,
                                implications            = EXCLUDED.implications,
                                meta_description        = COALESCE(EXCLUDED.meta_description, content.meta_description),
                                version                 = content.version + 1,
                                updated_at              = NOW()
                            RETURNING id, (xmax = 0) AS created
                            """,
                            (
                                record.filing_id,
                                record.company_id,
                                slug,
                                record.executive_summary,
                                as_jsonb(record.key_takeaways),
                                record.deep_dive_opportunities,
                                record.deep_dive_risks,
                                record.deep_dive_strategy,
                                record.implications,
                                record.meta_description,
                            ),
                        )
                        row = cur.fetchone()
                    return UpsertResult(id=str(row['id']), created=row['created'])

                except IntegrityError as exc:
                    if 'slug' not in str(exc).lower() or attempt == self._SLUG_ATTEMPTS - 1:
                        raise
                    log.warning(
                        "Slug %r already taken by another filing, disambiguating", slug
                    )

        raise IntegrityError(f"Could not find a free slug derived from {base_slug!r}")

    @staticmethod
    def _disambiguate(base_slug: str, filing_id: str, attempt: int) -> str:
        suffix = str(filing_id).replace('-', '')[: 4 + attempt]
        return f"{base_slug}-{suffix}"

    def set_html(self, content_id: str, column: str, html: str) -> None:
        """
        Store generated HTML.

        ``column`` is validated against an allowlist rather than interpolated
        blind — it is the one piece of these statements that is not a bind
        parameter, so it must not come from caller-controlled input unchecked.
        """
        allowed = {'blog_html', 'email_html'}
        if column not in allowed:
            raise DatabaseError(
                f"Refusing to write unknown content column {column!r}; expected one of {sorted(allowed)}"
            )

        with transaction(self.conn) as cur:
            cur.execute(
                f"UPDATE content SET {column} = %s, updated_at = NOW() WHERE id = %s",
                (html, content_id),
            )
            if cur.rowcount == 0:
                raise RecordNotFound(f"Content {content_id} not found")

    def mark_published(self, content_id: str) -> None:
        """Set ``published_at`` once. Re-publishing keeps the original timestamp."""
        with transaction(self.conn) as cur:
            cur.execute(
                """
                UPDATE content
                SET published_at = COALESCE(published_at, NOW()),
                    updated_at   = NOW()
                WHERE id = %s
                """,
                (content_id,),
            )
            if cur.rowcount == 0:
                raise RecordNotFound(f"Content {content_id} not found")

    def get_for_rendering(self, content_id: str) -> Dict[str, Any]:
        """Content joined with its filing and company, as a dict."""
        with read_cursor(self.conn) as cur:
            cur.execute(
                """
                SELECT
                    ct.id AS content_id,
                    ct.executive_summary,
                    ct.key_takeaways,
                    ct.deep_dive_opportunities,
                    ct.deep_dive_risks,
                    ct.deep_dive_strategy,
                    ct.implications,
                    ct.published_at,
                    ct.slug,
                    co.ticker,
                    co.name AS company_name,
                    f.filing_type,
                    f.fiscal_year,
                    f.fiscal_quarter,
                    f.filing_date
                FROM content ct
                JOIN filings f  ON ct.filing_id = f.id
                JOIN companies co ON f.company_id = co.id
                WHERE ct.id = %s
                """,
                (content_id,),
            )
            row = cur.fetchone()

        if row is None:
            raise RecordNotFound(f"Content {content_id} not found")
        return dict(row)

    def pending_generation(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        sql = """
            SELECT ct.id AS content_id, ct.filing_id, co.ticker, f.filing_type,
                   (ct.blog_html IS NULL)  AS needs_blog,
                   (ct.email_html IS NULL) AS needs_email
            FROM content ct
            JOIN filings f   ON ct.filing_id = f.id
            JOIN companies co ON f.company_id = co.id
            WHERE ct.is_current
              AND (ct.blog_html IS NULL OR ct.email_html IS NULL)
            ORDER BY ct.created_at DESC
        """
        params: List[Any] = []
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)

        with read_cursor(self.conn) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def count_pending_generation(self) -> int:
        with read_cursor(self.conn) as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM content
                WHERE is_current AND (blog_html IS NULL OR email_html IS NULL)
                """
            )
            return int(cur.fetchone()['n'])

    def ready_to_publish(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        sql = """
            SELECT ct.id AS content_id, ct.filing_id, co.ticker, f.filing_type,
                   COALESCE(ct.key_takeaways->>'headline', ct.executive_summary) AS headline
            FROM content ct
            JOIN filings f   ON ct.filing_id = f.id
            JOIN companies co ON f.company_id = co.id
            WHERE ct.is_current
              AND ct.email_html IS NOT NULL
              AND ct.published_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM email_deliveries d
                  WHERE d.content_id = ct.id AND d.status = 'sent'
              )
            ORDER BY ct.created_at DESC
        """
        params: List[Any] = []
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)

        with read_cursor(self.conn) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    def count_ready_to_publish(self) -> int:
        with read_cursor(self.conn) as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS n FROM content
                WHERE is_current AND email_html IS NOT NULL AND published_at IS NULL
                """
            )
            return int(cur.fetchone()['n'])


class MarketDataRepository(Repository):
    """Writes for ``company_market_data``."""

    def upsert_many(self, records: Sequence[MarketDataRecord]) -> Dict[str, int]:
        """
        Upsert a batch, isolating each row in a savepoint.

        The previous implementation shared one transaction with no savepoints,
        so the first bad row aborted the transaction and every later row failed
        with ``InFailedSqlTransaction`` — while the counter kept incrementing
        and the trailing ``commit()`` raised outside the try block.
        """
        return _upsert_batch(
            self.conn,
            records,
            self._write_one,
            label='market data',
            key=lambda r: r.ticker,
        )

    @staticmethod
    def _write_one(cur, record: MarketDataRecord) -> bool:
        record.validate()
        cur.execute(
            """
            INSERT INTO company_market_data (
                company_id, ticker, price, market_cap, volume,
                change_percent, data_date, fetched_at, source
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)
            ON CONFLICT (company_id, data_date) DO UPDATE SET
                price          = EXCLUDED.price,
                market_cap     = EXCLUDED.market_cap,
                volume         = EXCLUDED.volume,
                change_percent = EXCLUDED.change_percent,
                fetched_at     = EXCLUDED.fetched_at,
                source         = EXCLUDED.source
            RETURNING (xmax = 0) AS created
            """,
            (
                record.company_id,
                record.ticker,
                record.price,
                record.market_cap,
                record.volume,
                record.change_percent,
                record.data_date,
                record.source,
            ),
        )
        return bool(cur.fetchone()['created'])


class EarningsRepository(Repository):
    """Writes for ``scheduled_earnings``."""

    def upsert_many(self, records: Sequence[EarningsRecord]) -> Dict[str, int]:
        return _upsert_batch(
            self.conn,
            records,
            self._write_one,
            label='earnings event',
            key=lambda r: r.ticker,
        )

    @staticmethod
    def _write_one(cur, record: EarningsRecord) -> bool:
        record.validate()
        # Conflict target matches the expression index from migration 010.
        # The original UNIQUE(company_id, fiscal_year, fiscal_quarter) never
        # matched annual rows, because in Postgres NULL != NULL — so every 10-K
        # earnings date was re-inserted on every run.
        cur.execute(
            """
            INSERT INTO scheduled_earnings (
                company_id, ticker, earnings_date, earnings_time,
                fiscal_year, fiscal_quarter, eps_estimate, revenue_estimate,
                status, source, fetched_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (company_id, fiscal_year, COALESCE(fiscal_quarter, 0)) DO UPDATE SET
                earnings_date    = EXCLUDED.earnings_date,
                earnings_time    = COALESCE(EXCLUDED.earnings_time, scheduled_earnings.earnings_time),
                eps_estimate     = COALESCE(EXCLUDED.eps_estimate, scheduled_earnings.eps_estimate),
                revenue_estimate = COALESCE(EXCLUDED.revenue_estimate, scheduled_earnings.revenue_estimate),
                fetched_at       = EXCLUDED.fetched_at,
                updated_at       = EXCLUDED.updated_at
            RETURNING (xmax = 0) AS created
            """,
            (
                record.company_id,
                record.ticker,
                record.earnings_date,
                record.earnings_time,
                record.fiscal_year,
                record.fiscal_quarter,
                record.eps_estimate,
                record.revenue_estimate,
                record.status,
                record.source,
            ),
        )
        return bool(cur.fetchone()['created'])


class DeliveryRepository(Repository):
    """Writes for ``email_deliveries``."""

    def record(self, delivery: DeliveryRecord) -> str:
        delivery.validate()
        with transaction(self.conn, dict_rows=True) as cur:
            cur.execute(
                """
                INSERT INTO email_deliveries (
                    content_id, subscriber_id, status, sent_at,
                    resend_email_id, metadata
                )
                VALUES (%s, %s, %s, COALESCE(%s, NOW()), %s, %s)
                RETURNING id
                """,
                (
                    delivery.content_id,
                    delivery.subscriber_id,
                    delivery.status,
                    delivery.sent_at,
                    delivery.resend_email_id,
                    as_jsonb(delivery.metadata),
                ),
            )
            return str(cur.fetchone()['id'])

    def record_many(self, deliveries: Sequence[DeliveryRecord]) -> Dict[str, int]:
        return _upsert_batch(
            self.conn,
            deliveries,
            lambda cur, d: bool(self._insert(cur, d)),
            label='delivery record',
            key=lambda d: d.content_id,
        )

    @staticmethod
    def _insert(cur, delivery: DeliveryRecord) -> str:
        delivery.validate()
        cur.execute(
            """
            INSERT INTO email_deliveries (
                content_id, subscriber_id, status, sent_at,
                resend_email_id, metadata
            )
            VALUES (%s, %s, %s, COALESCE(%s, NOW()), %s, %s)
            RETURNING id
            """,
            (
                delivery.content_id,
                delivery.subscriber_id,
                delivery.status,
                delivery.sent_at,
                delivery.resend_email_id,
                as_jsonb(delivery.metadata),
            ),
        )
        return str(cur.fetchone()['id'])


class ProcessingLogRepository(Repository):
    """
    Writes for ``processing_logs``.

    Used by ``PipelineLogger`` on a *dedicated* connection. Writing logs on the
    shared pipeline connection meant every ``logger.info()`` committed whatever
    work was in flight, which silently defeated transactional writes everywhere.
    """

    def write(self, record: ProcessingLogRecord) -> None:
        record.validate()
        with transaction(self.conn) as cur:
            cur.execute(
                """
                INSERT INTO processing_logs (step, filing_id, level, status, message, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    record.step,
                    record.filing_id,
                    record.level,
                    record.status,
                    record.message,
                    as_jsonb(record.metadata),
                ),
            )


class SubscriberRepository(Repository):
    """
    Reads for ``subscribers``.

    Column names here follow migrations 002 and 007. The publisher previously
    selected ``enabled``, ``first_name`` and ``topics_subscribed`` — none of
    which exist; those names come from SCHEMA.md, which drifted from the actual
    migrations. Every audience query therefore raised UndefinedColumn.
    """

    def active(
        self,
        tier: Optional[str] = None,
        company_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        # email_frequency is constrained to ('daily', 'per_filing', 'disabled')
        # by migration 007. The migration-002 comment still says "daily, weekly,
        # off"; 'off' is not a legal value and filtering on it excludes nobody.
        sql = """
            SELECT id, email, subscription_tier, content_preference,
                   email_frequency, interested_companies
            FROM subscribers
            WHERE unsubscribed_at IS NULL
              AND COALESCE(email_enabled, true) = true
              AND COALESCE(email_frequency, 'daily') <> 'disabled'
        """
        params: List[Any] = []

        if tier and tier != 'all':
            sql += " AND subscription_tier = %s"
            params.append(tier)

        if company_id:
            # An empty or NULL interest list means "everything", which is the
            # sensible default for a newsletter signup with no preferences set.
            sql += """
              AND (
                  interested_companies IS NULL
                  OR cardinality(interested_companies) = 0
                  OR %s = ANY(interested_companies)
              )
            """
            params.append(company_id)

        sql += " ORDER BY subscribed_at"

        with read_cursor(self.conn) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def _upsert_batch(
    conn,
    records: Sequence[Any],
    write_one,
    *,
    label: str,
    key,
) -> Dict[str, int]:
    """
    Run a per-row write inside its own savepoint, then commit once.

    This is the shared shape for all batch inserts:

    - one transaction for the whole batch (one fsync, not N),
    - one savepoint per row, so a bad row rolls back alone,
    - counts that reflect what the database actually accepted.
    """
    stats = {'created': 0, 'updated': 0, 'failed': 0, 'total': len(records)}
    if not records:
        return stats

    with transaction(conn):
        for record in records:
            try:
                with savepoint(conn, dict_rows=True) as cur:
                    created = write_one(cur, record)
                stats['created' if created else 'updated'] += 1
            except DatabaseError as exc:
                stats['failed'] += 1
                log.error("Failed to save %s for %s: %s", label, key(record), exc)

    return stats
