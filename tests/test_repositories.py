"""
Integration tests for the data access layer (pipeline/db/).

These need a real PostgreSQL instance because the behaviour under test *is*
PostgreSQL behaviour: ON CONFLICT targets, savepoint isolation, partial unique
indexes, NULL semantics in unique constraints. A mock would assert nothing.

Point TEST_DATABASE_URL at a scratch database with all migrations applied:

    createdb tenkay_test
    for m in migrations/*.sql; do psql tenkay_test -f "$m"; done
    TEST_DATABASE_URL=postgresql://localhost/tenkay_test python3 tests/test_repositories.py

Skips (exit 0) when TEST_DATABASE_URL is unset, so CI without a database stays
green rather than red-for-the-wrong-reason.
"""
import os
import sys
import uuid
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DSN = os.getenv('TEST_DATABASE_URL')
if not DSN:
    print("TEST_DATABASE_URL not set - skipping database integration tests")
    sys.exit(0)

from pipeline.db import (  # noqa: E402
    CompanyRepository,
    ContentRecord,
    ContentRepository,
    DeliveryRecord,
    DeliveryRepository,
    EarningsRecord,
    EarningsRepository,
    FilingRecord,
    FilingRepository,
    IntegrityError,
    MarketDataRecord,
    MarketDataRepository,
    RecordNotFound,
    ValidationError,
    build_slug,
    connect,
    read_cursor,
    savepoint,
    transaction,
)


def fresh_ticker() -> str:
    return 'T' + uuid.uuid4().hex[:6].upper()


def fresh_accession() -> str:
    return f"{uuid.uuid4().int % 10**10:010d}-25-{uuid.uuid4().int % 1000:06d}"


# --------------------------------------------------------------- transactions

def test_transaction_commits_on_success(conn):
    ticker = fresh_ticker()
    CompanyRepository(conn).upsert(ticker, 'Test Co')
    conn.rollback()  # would discard it if the upsert had not committed
    assert CompanyRepository(conn).find_id(ticker) is not None


def test_transaction_rolls_back_on_error(conn):
    ticker = fresh_ticker()
    try:
        with transaction(conn) as cur:
            cur.execute(
                "INSERT INTO companies (ticker, name) VALUES (%s, %s)", (ticker, 'Doomed')
            )
            cur.execute("SELECT 1/0")
    except Exception:
        pass
    assert CompanyRepository(conn).find_id(ticker) is None


def test_savepoint_isolates_a_failing_row(conn):
    """The core batch-loop fix: a bad row must not abort its siblings."""
    good_a, good_b, bad = fresh_ticker(), fresh_ticker(), fresh_ticker()

    with transaction(conn) as cur:
        cur.execute("INSERT INTO companies (ticker, name) VALUES (%s, %s)", (good_a, 'A'))

        try:
            with savepoint(conn) as sp:
                sp.execute("INSERT INTO companies (ticker, name) VALUES (%s, NULL)", (bad,))
        except IntegrityError:
            pass  # name is NOT NULL

        # Without the savepoint this statement would raise InFailedSqlTransaction.
        cur.execute("INSERT INTO companies (ticker, name) VALUES (%s, %s)", (good_b, 'B'))

    repo = CompanyRepository(conn)
    assert repo.find_id(good_a) is not None
    assert repo.find_id(good_b) is not None
    assert repo.find_id(bad) is None


def test_nested_transaction_does_not_commit_the_outer_one(conn):
    ticker_outer, ticker_inner = fresh_ticker(), fresh_ticker()
    try:
        with transaction(conn) as cur:
            cur.execute(
                "INSERT INTO companies (ticker, name) VALUES (%s, %s)", (ticker_outer, 'Outer')
            )
            # A helper that opens its own transaction, called from inside one.
            with transaction(conn) as inner:
                inner.execute(
                    "INSERT INTO companies (ticker, name) VALUES (%s, %s)", (ticker_inner, 'Inner')
                )
            raise RuntimeError('outer fails after the inner block succeeded')
    except RuntimeError:
        pass

    repo = CompanyRepository(conn)
    assert repo.find_id(ticker_outer) is None, 'outer work must roll back'
    assert repo.find_id(ticker_inner) is None, 'inner must not have committed early'


def test_read_cursor_leaves_no_open_transaction(conn):
    with read_cursor(conn) as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
    import psycopg2.extensions
    assert conn.status == psycopg2.extensions.STATUS_READY


# ------------------------------------------------------------------- filings

def test_filing_upsert_is_idempotent(conn, company_id):
    accession = fresh_accession()
    record = FilingRecord(
        company_id=company_id,
        filing_type='10-Q',
        accession_number=accession,
        filing_date=date(2025, 5, 1),
        edgar_url='https://sec.gov/x',
        raw_document_url=None,
        fiscal_year=2025,
        fiscal_quarter=1,
    )
    repo = FilingRepository(conn)

    first = repo.upsert(record)
    assert first.created is True

    # Re-fetch: same filing, now with an S3 URL. Used to raise a unique violation.
    record.raw_document_url = 's3://bucket/key.html'
    second = repo.upsert(record)
    assert second.created is False
    assert second.id == first.id

    context = repo.get_context(first.id)
    assert context['raw_document_url'] == 's3://bucket/key.html'
    assert context['fiscal_period'] == 'Q1'


def test_filing_upsert_does_not_reset_an_analyzed_status(conn, company_id):
    accession = fresh_accession()
    repo = FilingRepository(conn)
    record = FilingRecord(
        company_id=company_id, filing_type='10-K', accession_number=accession,
        filing_date=date(2025, 1, 1), edgar_url='https://sec.gov/y', fiscal_year=2025,
    )
    filing_id = repo.upsert(record).id
    repo.set_status(filing_id, 'analyzed', processed=True)

    repo.upsert(record)  # a re-fetch on the next pipeline run

    assert repo.get_context(filing_id)['status'] == 'analyzed', \
        're-fetching must not send an analyzed filing back to pending'


def test_filing_record_validates_before_sql(conn, company_id):
    try:
        FilingRepository(conn).upsert(FilingRecord(
            company_id=company_id, filing_type='10-Q', accession_number=fresh_accession(),
            filing_date=date(2025, 1, 1), edgar_url='https://sec.gov/z',
            fiscal_year=2025, fiscal_quarter=None,  # a 10-Q needs a quarter
        ))
    except ValidationError as exc:
        assert 'fiscal_quarter' in str(exc)
    else:
        raise AssertionError('expected ValidationError')


# ------------------------------------------------------------------- content

def _content_record(filing_id, company_id, ticker, **overrides):
    payload = dict(
        filing_id=filing_id,
        company_id=company_id,
        slug=build_slug(ticker, '10-Q', 2025, 1),
        executive_summary='Summary text.',
        key_takeaways={'headline': 'H', 'points': []},
    )
    payload.update(overrides)
    return ContentRecord(**payload)


def test_content_upsert_is_idempotent_and_versions(conn, company_id, ticker):
    filing_id = FilingRepository(conn).upsert(FilingRecord(
        company_id=company_id, filing_type='10-Q', accession_number=fresh_accession(),
        filing_date=date(2025, 5, 1), edgar_url='https://sec.gov/a',
        fiscal_year=2025, fiscal_quarter=1,
    )).id

    repo = ContentRepository(conn)
    first = repo.upsert_analysis(_content_record(filing_id, company_id, ticker))
    assert first.created is True

    # Re-analysis of the same filing: same row, version bumped, no collision.
    second = repo.upsert_analysis(_content_record(
        filing_id, company_id, ticker, executive_summary='Revised summary.'
    ))
    assert second.created is False
    assert second.id == first.id

    with read_cursor(conn) as cur:
        cur.execute("SELECT version, executive_summary FROM content WHERE id = %s", (first.id,))
        row = cur.fetchone()
    assert row['version'] == 2
    assert row['executive_summary'] == 'Revised summary.'


def test_content_upsert_disambiguates_a_colliding_slug(conn, company_id, ticker):
    """
    content.slug is UNIQUE. Two filings can derive the same slug when they
    differ only in a field the slug does not encode, so the upsert must fall
    back to a disambiguated slug instead of failing the write.
    """
    repo = ContentRepository(conn)
    filing_ids = []
    # Different fiscal quarters keep idx_filings_unique happy; we then force the
    # identical slug onto both content rows.
    for quarter in (1, 2):
        filing_ids.append(FilingRepository(conn).upsert(FilingRecord(
            company_id=company_id, filing_type='10-Q', accession_number=fresh_accession(),
            filing_date=date(2025, 5, 1), edgar_url='https://sec.gov/b',
            fiscal_year=2025, fiscal_quarter=quarter,
        )).id)

    shared_slug = build_slug(ticker, '10-Q', 2025, 1)
    first = repo.upsert_analysis(
        _content_record(filing_ids[0], company_id, ticker, slug=shared_slug)
    )
    second = repo.upsert_analysis(
        _content_record(filing_ids[1], company_id, ticker, slug=shared_slug)
    )

    assert first.id != second.id
    with read_cursor(conn) as cur:
        cur.execute(
            "SELECT slug FROM content WHERE id = ANY(%s::uuid[])",
            ([first.id, second.id],),
        )
        slugs = sorted(row['slug'] for row in cur.fetchall())
    assert len(set(slugs)) == 2, f'slugs must be distinct, got {slugs}'
    assert all(s.startswith(shared_slug) for s in slugs)


def test_amended_filing_supersedes_the_period(conn, company_id):
    """
    filings has a *second* unique index on (company_id, filing_type,
    fiscal_year, COALESCE(fiscal_quarter, 0)). An amended filing brings a new
    accession number for a period that already exists, so it collides there and
    not on accession_number — which ON CONFLICT (accession_number) cannot catch.
    """
    repo = FilingRepository(conn)
    original = repo.upsert(FilingRecord(
        company_id=company_id, filing_type='10-Q', accession_number=fresh_accession(),
        filing_date=date(2025, 5, 1), edgar_url='https://sec.gov/orig',
        fiscal_year=2025, fiscal_quarter=2,
    ))
    assert original.created is True

    amended_accession = fresh_accession()
    amended = repo.upsert(FilingRecord(
        company_id=company_id, filing_type='10-Q', accession_number=amended_accession,
        filing_date=date(2025, 5, 15), edgar_url='https://sec.gov/amended',
        fiscal_year=2025, fiscal_quarter=2,
        raw_document_url='s3://bucket/amended.html',
    ))

    assert amended.created is False
    assert amended.id == original.id, 'the amendment supersedes the same row'

    context = repo.get_context(original.id)
    assert context['accession_number'] == amended_accession
    assert context['raw_document_url'] == 's3://bucket/amended.html'


def test_transaction_preserves_non_database_exception_types(conn):
    """A bug inside a transaction block must not be relabelled DatabaseError."""
    class AppError(Exception):
        pass

    try:
        with transaction(conn) as cur:
            cur.execute("SELECT 1")
            raise AppError('business logic said no')
    except AppError:
        pass
    else:
        raise AssertionError('AppError should have propagated unchanged')


def test_content_requires_a_summary(conn, company_id, ticker):
    filing_id = FilingRepository(conn).upsert(FilingRecord(
        company_id=company_id, filing_type='10-K', accession_number=fresh_accession(),
        filing_date=date(2025, 1, 1), edgar_url='https://sec.gov/c', fiscal_year=2025,
    )).id
    try:
        ContentRepository(conn).upsert_analysis(_content_record(
            filing_id, company_id, ticker, executive_summary=''
        ))
    except ValidationError as exc:
        assert 'executive_summary' in str(exc)
    else:
        raise AssertionError('expected ValidationError')


def test_set_html_rejects_an_unknown_column(conn, company_id, ticker):
    filing_id = FilingRepository(conn).upsert(FilingRecord(
        company_id=company_id, filing_type='10-K', accession_number=fresh_accession(),
        filing_date=date(2025, 1, 1), edgar_url='https://sec.gov/d', fiscal_year=2025,
    )).id
    content_id = ContentRepository(conn).upsert_analysis(
        _content_record(filing_id, company_id, ticker)
    ).id

    try:
        ContentRepository(conn).set_html(content_id, 'executive_summary; DROP TABLE x', '<p></p>')
    except Exception as exc:
        assert 'unknown content column' in str(exc)
    else:
        raise AssertionError('expected the column allowlist to reject this')

    ContentRepository(conn).set_html(content_id, 'blog_html', '<p>ok</p>')


def test_set_html_raises_when_the_row_is_gone(conn):
    try:
        ContentRepository(conn).set_html(str(uuid.uuid4()), 'blog_html', '<p>x</p>')
    except RecordNotFound:
        pass
    else:
        raise AssertionError('a no-op UPDATE must not report success')


# --------------------------------------------------------------- batch writes

def test_market_data_batch_survives_a_bad_row(conn, company_id, ticker):
    """A poisoned row used to take every later row in the batch with it."""
    records = [
        MarketDataRecord(company_id=company_id, ticker=ticker,
                         data_date=date(2025, 1, 1), price=1.0),
        MarketDataRecord(company_id=str(uuid.uuid4()), ticker='BAD',
                         data_date=date(2025, 1, 2), price=2.0),  # FK violation
        MarketDataRecord(company_id=company_id, ticker=ticker,
                         data_date=date(2025, 1, 3), price=3.0),
    ]
    stats = MarketDataRepository(conn).upsert_many(records)

    assert stats['created'] == 2, f'both good rows must land: {stats}'
    assert stats['failed'] == 1

    with read_cursor(conn) as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM company_market_data WHERE company_id = %s", (company_id,)
        )
        assert cur.fetchone()['n'] == 2


def test_market_data_upsert_updates_the_same_day(conn, company_id, ticker):
    repo = MarketDataRepository(conn)
    day = date(2025, 3, 3)
    repo.upsert_many([MarketDataRecord(
        company_id=company_id, ticker=ticker, data_date=day, price=10.0
    )])
    stats = repo.upsert_many([MarketDataRecord(
        company_id=company_id, ticker=ticker, data_date=day, price=11.0
    )])

    assert stats['updated'] == 1 and stats['created'] == 0
    with read_cursor(conn) as cur:
        cur.execute(
            "SELECT price FROM company_market_data WHERE company_id = %s AND data_date = %s",
            (company_id, day),
        )
        assert float(cur.fetchone()['price']) == 11.0


def test_annual_earnings_deduplicate_despite_a_null_quarter(conn, company_id, ticker):
    """
    The regression migration 010 fixes: UNIQUE(company_id, fiscal_year,
    fiscal_quarter) never matched NULL quarters, so every run duplicated 10-K
    earnings rows.
    """
    repo = EarningsRepository(conn)
    record = EarningsRecord(
        company_id=company_id, ticker=ticker,
        earnings_date=date(2025, 2, 20), fiscal_year=2025, fiscal_quarter=None,
    )

    assert repo.upsert_many([record])['created'] == 1
    record.earnings_date = date(2025, 2, 25)
    stats = repo.upsert_many([record])
    assert stats['updated'] == 1 and stats['created'] == 0

    with read_cursor(conn) as cur:
        cur.execute(
            "SELECT COUNT(*) AS n, MAX(earnings_date) AS d FROM scheduled_earnings "
            "WHERE company_id = %s AND fiscal_quarter IS NULL",
            (company_id,),
        )
        row = cur.fetchone()
    assert row['n'] == 1, 'annual earnings must not duplicate'
    assert row['d'] == date(2025, 2, 25), 'the update must have applied'


def test_delivery_record_writes_metadata(conn, company_id, ticker):
    """email_deliveries.metadata did not exist before migration 010."""
    filing_id = FilingRepository(conn).upsert(FilingRecord(
        company_id=company_id, filing_type='10-K', accession_number=fresh_accession(),
        filing_date=date(2025, 1, 1), edgar_url='https://sec.gov/e', fiscal_year=2025,
    )).id
    content_id = ContentRepository(conn).upsert_analysis(
        _content_record(filing_id, company_id, ticker)
    ).id

    delivery_id = DeliveryRepository(conn).record(DeliveryRecord(
        content_id=content_id, status='sent', sent_at=datetime.now(),
        resend_email_id='re_123', metadata={'recipient_count': 42, 'tier': 'paid'},
    ))

    with read_cursor(conn) as cur:
        cur.execute("SELECT metadata FROM email_deliveries WHERE id = %s", (delivery_id,))
        assert cur.fetchone()['metadata']['recipient_count'] == 42


# ------------------------------------------------------------------- queues

def test_pending_excludes_filings_that_already_have_content(conn, company_id, ticker):
    """A crash can leave status='pending' after content was written."""
    filing_id = FilingRepository(conn).upsert(FilingRecord(
        company_id=company_id, filing_type='10-K', accession_number=fresh_accession(),
        filing_date=date(2025, 6, 1), edgar_url='https://sec.gov/f', fiscal_year=2025,
    )).id

    pending_ids = {str(f['filing_id']) for f in FilingRepository(conn).pending(limit=500)}
    assert filing_id in pending_ids

    ContentRepository(conn).upsert_analysis(_content_record(filing_id, company_id, ticker))

    pending_ids = {str(f['filing_id']) for f in FilingRepository(conn).pending(limit=500)}
    assert filing_id not in pending_ids, 'must not re-pay Bedrock for an analyzed filing'


def test_limit_is_bound_not_interpolated(conn):
    # A value that would be a syntax error if it were spliced into the SQL text.
    assert FilingRepository(conn).pending(limit=1) is not None
    try:
        FilingRepository(conn).pending(limit="1; DROP TABLE content")
    except Exception:
        pass  # rejected as a parameter, which is the point
    with read_cursor(conn) as cur:
        cur.execute("SELECT to_regclass('content') AS t")
        assert cur.fetchone()['t'] is not None, 'content table must still exist'


def main():
    conn = connect(DSN, application_name='10kay-tests')

    ticker = fresh_ticker()
    company_id = CompanyRepository(conn).upsert(ticker, 'Fixture Co').id

    tests = [
        (name, fn) for name, fn in sorted(globals().items())
        if name.startswith('test_') and callable(fn)
    ]

    failures = []
    for name, fn in tests:
        # Each test gets fresh fixtures so ordering cannot matter.
        local_ticker = fresh_ticker()
        local_company = CompanyRepository(conn).upsert(local_ticker, 'Fixture Co').id
        kwargs = {}
        params = fn.__code__.co_varnames[:fn.__code__.co_argcount]
        if 'conn' in params:
            kwargs['conn'] = conn
        if 'company_id' in params:
            kwargs['company_id'] = local_company
        if 'ticker' in params:
            kwargs['ticker'] = local_ticker

        try:
            fn(**kwargs)
        except Exception as exc:  # noqa: BLE001 - this is a test runner
            failures.append(name)
            print(f"FAIL {name}: {type(exc).__name__}: {exc}")
            try:
                conn.rollback()
            except Exception:
                conn = connect(DSN)
        else:
            print(f"ok   {name}")

    print(f"\n{len(tests) - len(failures)}/{len(tests)} passed")
    conn.close()
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
