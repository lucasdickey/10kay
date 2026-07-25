"""
Connection and transaction management for the 10KAY pipeline.

Every write in this codebase used to follow the same hand-rolled shape::

    cursor = self.db_connection.cursor()
    cursor.execute(...)
    self.db_connection.commit()
    cursor.close()          # skipped on the error path
    except Exception:
        self.db_connection.rollback()

That pattern has three failure modes this module removes:

1. **Leaked cursors.** ``cursor.close()`` sits after the statement, so any
   exception leaks it. ``transaction()`` / ``read_cursor()`` close in ``finally``.

2. **Poisoned transactions in batch loops.** In psycopg2 a single failed
   statement aborts the whole transaction; every subsequent statement raises
   ``InFailedSqlTransaction`` until a rollback. Loops that caught the error and
   ``continue``-d therefore lost *all* remaining rows, not just the bad one.
   ``savepoint()`` scopes each iteration so one bad row rolls back alone.

3. **Nested commits.** ``transaction()`` is re-entrant: opening one while another
   is already active on the same connection degrades to a savepoint instead of
   committing the outer unit of work early.

Usage::

    with transaction(conn) as cur:              # commits on exit, rolls back on error
        cur.execute("INSERT ...")

    for row in rows:                            # one bad row does not kill the batch
        try:
            with savepoint(conn) as cur:
                cur.execute("INSERT ...", row)
        except IntegrityError:
            continue

    with read_cursor(conn) as cur:              # no idle-in-transaction leak
        cur.execute("SELECT ...")
"""
from __future__ import annotations

import contextlib
import itertools
import logging
import threading
import time
from typing import Any, Callable, Iterator, Optional, TypeVar

import psycopg2
import psycopg2.extensions
import psycopg2.extras
from psycopg2 import errors as pg_errors
from psycopg2.pool import ThreadedConnectionPool

from .errors import (
    DatabaseError,
    IntegrityError,
    RecordNotFound,
    TransientDatabaseError,
)

__all__ = [
    'connect',
    'transaction',
    'savepoint',
    'read_cursor',
    'translate_error',
    'with_retry',
    'ConnectionPool',
]

log = logging.getLogger(__name__)

T = TypeVar('T')

# Transaction depth per connection, so transaction() can detect re-entry.
# Keyed by id(conn); entries are removed when depth returns to zero.
_depth: dict[int, int] = {}
_depth_lock = threading.Lock()
_savepoint_counter = itertools.count()

# psycopg2 error classes that mean "the database or connection hiccuped".
_TRANSIENT = (
    psycopg2.OperationalError,
    psycopg2.InterfaceError,
    pg_errors.DeadlockDetected,
    pg_errors.SerializationFailure,
    pg_errors.LockNotAvailable,
)


def connect(
    dsn: str,
    *,
    autocommit: bool = False,
    application_name: str = '10kay-pipeline',
    connect_timeout: int = 10,
) -> psycopg2.extensions.connection:
    """
    Open a connection with the settings the pipeline expects.

    ``application_name`` shows up in ``pg_stat_activity``, which makes it
    possible to tell a runaway backfill worker apart from the web app.
    """
    try:
        conn = psycopg2.connect(
            dsn,
            application_name=application_name,
            connect_timeout=connect_timeout,
        )
    except psycopg2.Error as exc:
        raise translate_error(exc, 'connect') from exc

    conn.autocommit = autocommit
    return conn


def translate_error(exc: BaseException, context: str = '') -> BaseException:
    """
    Map a psycopg2 exception onto the pipeline error taxonomy.

    Keeping this in one place means callers never have to string-match on
    ``'duplicate key value violates unique constraint'``.

    Exceptions that did not come from the database are returned unchanged: a
    ``ValueError`` raised inside a ``with transaction(...)`` block is a bug in
    that block, and relabelling it ``DatabaseError`` sends whoever reads the
    traceback to the wrong place.
    """
    prefix = f"{context}: " if context else ''

    if isinstance(exc, DatabaseError):
        return exc
    if isinstance(exc, _TRANSIENT):
        return TransientDatabaseError(f"{prefix}{exc}")
    if isinstance(exc, psycopg2.IntegrityError):
        return IntegrityError(f"{prefix}{exc}")
    if isinstance(exc, psycopg2.Error):
        return DatabaseError(f"{prefix}{exc}")
    return exc


def _cursor_factory(dict_rows: bool):
    return psycopg2.extras.RealDictCursor if dict_rows else None


@contextlib.contextmanager
def transaction(
    conn: psycopg2.extensions.connection,
    *,
    dict_rows: bool = False,
) -> Iterator[psycopg2.extensions.cursor]:
    """
    Run a unit of work: commit on clean exit, roll back on any exception.

    Re-entrant. A nested ``transaction()`` on the same connection becomes a
    savepoint, so a helper that opens its own transaction can be safely called
    from inside a larger one without committing it halfway through.
    """
    key = id(conn)
    with _depth_lock:
        depth = _depth.get(key, 0)

    if depth > 0:
        with savepoint(conn, dict_rows=dict_rows) as cur:
            yield cur
        return

    with _depth_lock:
        _depth[key] = 1

    cursor = conn.cursor(cursor_factory=_cursor_factory(dict_rows))
    try:
        yield cursor
    except BaseException as exc:
        _safe_rollback(conn)
        _reraise(exc)
    else:
        try:
            conn.commit()
        except psycopg2.Error as exc:
            _safe_rollback(conn)
            raise translate_error(exc, 'commit') from exc
    finally:
        _close_quietly(cursor)
        with _depth_lock:
            _depth.pop(key, None)


@contextlib.contextmanager
def savepoint(
    conn: psycopg2.extensions.connection,
    *,
    dict_rows: bool = False,
) -> Iterator[psycopg2.extensions.cursor]:
    """
    Scope a single statement group so its failure does not abort the outer
    transaction. This is what makes per-row error handling in batch loops work.
    """
    if conn.autocommit:
        # Savepoints require an open transaction; in autocommit mode each
        # statement is already its own, so nothing to isolate.
        cursor = conn.cursor(cursor_factory=_cursor_factory(dict_rows))
        try:
            yield cursor
        except BaseException as exc:
            _reraise(exc)
        finally:
            _close_quietly(cursor)
        return

    name = f"sp_{next(_savepoint_counter)}"
    key = id(conn)
    with _depth_lock:
        _depth[key] = _depth.get(key, 0) + 1

    cursor = conn.cursor(cursor_factory=_cursor_factory(dict_rows))
    try:
        cursor.execute(f"SAVEPOINT {name}")
        yield cursor
    except BaseException as exc:
        try:
            cursor.execute(f"ROLLBACK TO SAVEPOINT {name}")
        except psycopg2.Error:
            # The connection itself is gone; the outer transaction is lost too.
            log.debug("Could not roll back to %s", name, exc_info=True)
        _reraise(exc)
    else:
        try:
            cursor.execute(f"RELEASE SAVEPOINT {name}")
        except psycopg2.Error as exc:
            raise translate_error(exc, 'release savepoint') from exc
    finally:
        _close_quietly(cursor)
        with _depth_lock:
            remaining = _depth.get(key, 1) - 1
            if remaining > 0:
                _depth[key] = remaining
            else:
                _depth.pop(key, None)


@contextlib.contextmanager
def read_cursor(
    conn: psycopg2.extensions.connection,
    *,
    dict_rows: bool = True,
) -> Iterator[psycopg2.extensions.cursor]:
    """
    Cursor for reads. Rolls back on exit so a long-lived connection does not sit
    ``idle in transaction`` holding row locks after a plain SELECT.

    Defaults to dict rows: positional ``row[7]`` indexing was a recurring source
    of silent column drift whenever a query grew a column.
    """
    cursor = conn.cursor(cursor_factory=_cursor_factory(dict_rows))
    nested = False
    with _depth_lock:
        nested = _depth.get(id(conn), 0) > 0
    try:
        yield cursor
    except BaseException as exc:
        _reraise(exc)
    finally:
        _close_quietly(cursor)
        if not nested and not conn.autocommit and not conn.closed:
            try:
                conn.rollback()
            except psycopg2.Error:
                log.debug("Rollback after read failed", exc_info=True)


def with_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
    description: str = 'database operation',
) -> T:
    """
    Retry ``fn`` on transient failures with exponential backoff.

    Only ``TransientDatabaseError`` is retried. Constraint violations and
    missing records are raised immediately: re-running them just burns time.
    """
    last: Optional[BaseException] = None

    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except TransientDatabaseError as exc:
            last = exc
            if attempt == attempts:
                break
            delay = base_delay * (2 ** (attempt - 1))
            log.warning(
                "%s failed (attempt %d/%d), retrying in %.1fs: %s",
                description, attempt, attempts, delay, exc,
            )
            time.sleep(delay)

    raise TransientDatabaseError(
        f"{description} failed after {attempts} attempts: {last}"
    )


class ConnectionPool:
    """
    Thread-safe connection pool for the parallel backfill scripts.

    Those scripts used to call ``psycopg2.connect()`` per work item and rely on
    ``conn.close()`` being reached — which it was not on the exception path, so
    long runs leaked backends until the server refused new connections.

    Usage::

        pool = ConnectionPool(dsn, maxconn=8)
        with pool.connection() as conn:
            with transaction(conn) as cur:
                ...
        pool.close()
    """

    def __init__(
        self,
        dsn: str,
        *,
        minconn: int = 1,
        maxconn: int = 8,
        application_name: str = '10kay-pipeline',
    ):
        self._dsn = dsn
        try:
            self._pool = ThreadedConnectionPool(
                minconn,
                maxconn,
                dsn,
                application_name=application_name,
                connect_timeout=10,
            )
        except psycopg2.Error as exc:
            raise translate_error(exc, 'create pool') from exc

    @contextlib.contextmanager
    def connection(self) -> Iterator[psycopg2.extensions.connection]:
        """Borrow a connection; always returned, even on exception."""
        try:
            conn = self._pool.getconn()
        except psycopg2.Error as exc:
            raise translate_error(exc, 'acquire connection') from exc

        broken = False
        try:
            conn.autocommit = False
            yield conn
        except TransientDatabaseError:
            broken = True
            raise
        finally:
            try:
                if not broken and not conn.closed and conn.status != psycopg2.extensions.STATUS_READY:
                    conn.rollback()
            except psycopg2.Error:
                broken = True
            self._pool.putconn(conn, close=broken or conn.closed)

    def close(self) -> None:
        """Close every pooled connection. Safe to call more than once."""
        try:
            self._pool.closeall()
        except psycopg2.Error:
            log.debug("Pool close failed", exc_info=True)

    def __enter__(self) -> 'ConnectionPool':
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


def _reraise(exc: BaseException, context: str = '') -> None:
    """
    Re-raise ``exc``, translated when it is a database error.

    Non-database exceptions propagate untouched (identity preserved), so
    ``except MyError`` around a ``with transaction(...)`` block still works.
    """
    translated = translate_error(exc, context)
    if translated is exc:
        raise
    raise translated from exc


def _safe_rollback(conn: psycopg2.extensions.connection) -> None:
    try:
        if not conn.closed:
            conn.rollback()
    except psycopg2.Error:
        log.debug("Rollback failed", exc_info=True)


def _close_quietly(cursor: psycopg2.extensions.cursor) -> None:
    try:
        cursor.close()
    except psycopg2.Error:
        log.debug("Cursor close failed", exc_info=True)
