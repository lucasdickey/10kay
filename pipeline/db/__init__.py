"""
Data access layer for the 10KAY pipeline.

Import writes from here rather than issuing SQL from fetchers, analyzers,
generators, publishers or one-off scripts::

    from pipeline.db import connect, transaction, FilingRepository, FilingRecord

    conn = connect(config.database.url)
    result = FilingRepository(conn).upsert(FilingRecord(...))

Layers:

- ``connection`` -- connections, transactions, savepoints, retry, pooling
- ``models``     -- typed, self-validating row contracts
- ``repositories`` -- idempotent upserts, one class per table
- ``errors``     -- the error taxonomy callers branch on
"""
from .connection import (
    ConnectionPool,
    connect,
    read_cursor,
    savepoint,
    transaction,
    translate_error,
    with_retry,
)
from .errors import (
    DatabaseError,
    IntegrityError,
    RecordNotFound,
    TransientDatabaseError,
)
from .models import (
    ContentRecord,
    DeliveryRecord,
    EarningsRecord,
    FilingRecord,
    MarketDataRecord,
    ProcessingLogRecord,
    UpsertResult,
    ValidationError,
    as_jsonb,
    build_slug,
)
from .repositories import (
    CompanyRepository,
    ContentRepository,
    DeliveryRepository,
    EarningsRepository,
    FilingRepository,
    MarketDataRepository,
    ProcessingLogRepository,
    SubscriberRepository,
)

__all__ = [
    # connection
    'ConnectionPool',
    'connect',
    'read_cursor',
    'savepoint',
    'transaction',
    'translate_error',
    'with_retry',
    # errors
    'DatabaseError',
    'IntegrityError',
    'RecordNotFound',
    'TransientDatabaseError',
    'ValidationError',
    # models
    'ContentRecord',
    'DeliveryRecord',
    'EarningsRecord',
    'FilingRecord',
    'MarketDataRecord',
    'ProcessingLogRecord',
    'UpsertResult',
    'as_jsonb',
    'build_slug',
    # repositories
    'CompanyRepository',
    'ContentRepository',
    'DeliveryRepository',
    'EarningsRepository',
    'FilingRepository',
    'MarketDataRepository',
    'ProcessingLogRepository',
    'SubscriberRepository',
]
