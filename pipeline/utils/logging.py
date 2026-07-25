"""
Logging utilities for the 10KAY pipeline.

Structured logging to stdout plus an audit trail in ``processing_logs``.

**Why this file changed.** The previous implementation persisted log rows on the
*same* connection the pipeline used for its work, and called ``commit()`` after
each insert::

    cursor = self.db_connection.cursor()
    cursor.execute("INSERT INTO processing_logs ...")
    self.db_connection.commit()          # <-- commits the caller's open work

Since analyzers, fetchers and publishers all log from inside their save methods,
every ``logger.info()`` committed whatever was in flight. A rollback after a
later failure could not undo the already-committed half, so "transactional"
writes were transactional in name only. It also meant one failed log insert
poisoned the caller's transaction.

Log rows now go through a **separate autocommit connection**, opened lazily from
the same DSN. Logging can no longer commit, abort or otherwise touch pipeline
work, and a logging outage degrades to stdout-only instead of failing the run.
"""
from __future__ import annotations

import logging
import sys
import threading
from enum import Enum
from typing import Any, Dict, Optional

__all__ = ['LogLevel', 'PipelineLogger', 'setup_root_logger']


class LogLevel(str, Enum):
    """Log levels matching the processing_logs.level column."""
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


class PipelineLogger:
    """
    Logger that writes to stdout and, optionally, to ``processing_logs``.

    Usage::

        logger = PipelineLogger('fetch_filings', db_connection=conn)
        logger.info('Starting to fetch filings')
        logger.error('Failed to fetch filing', extra={'filing_id': '123'})

    ``db_connection`` is used only to discover the DSN; log rows are written on
    a dedicated connection so they never interfere with the caller's
    transaction. Pass ``dsn=`` directly when no pipeline connection exists.
    """

    #: Levels below this are not persisted. Debug lines are high volume and low
    #: value in an audit table, and each one is a round trip.
    PERSIST_FROM = LogLevel.INFO

    _PERSIST_ORDER = {
        LogLevel.DEBUG: 10,
        LogLevel.INFO: 20,
        LogLevel.WARNING: 30,
        LogLevel.ERROR: 40,
        LogLevel.CRITICAL: 50,
    }

    def __init__(
        self,
        step: str,
        filing_id: Optional[str] = None,
        db_connection=None,
        name: Optional[str] = None,
        dsn: Optional[str] = None,
        persist: bool = True,
    ):
        """
        Args:
            step: Pipeline step name (e.g. 'fetch_filings'). Required, NOT NULL.
            filing_id: Optional filing ID recorded with every line.
            db_connection: Pipeline connection; used only to derive the DSN.
            name: Optional Python logger name (defaults to ``step``).
            dsn: Explicit database URL, when no connection is available.
            persist: Set False to disable database logging entirely.
        """
        if not step or not isinstance(step, str):
            # The old signature was PipelineLogger(root_logger, 'name'), which
            # several scripts still called; that put a Logger (or None) into a
            # NOT NULL column. Fail here, at the call site, instead.
            raise TypeError(
                f"PipelineLogger(step=...) expects a step name string, got "
                f"{type(step).__name__}. Did you mean PipelineLogger('{name or 'step'}')?"
            )

        self.step = step
        self.filing_id = filing_id
        self.persist = persist
        self._dsn = dsn or _dsn_from_connection(db_connection)
        self._log_conn = None
        self._log_lock = threading.Lock()
        self._persist_disabled_reason: Optional[str] = None

        self.logger = logging.getLogger(name or step)
        if not self.logger.handlers:
            root = logging.getLogger()
            if root.handlers:
                # setup_root_logger() already installed a handler. Adding another
                # here and letting records propagate printed every line twice.
                self.logger.setLevel(root.level)
            else:
                handler = logging.StreamHandler(sys.stdout)
                handler.setFormatter(
                    logging.Formatter(
                        '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                    )
                )
                self.logger.addHandler(handler)
                self.logger.propagate = False
                self.logger.setLevel(logging.INFO)

    # -- public API ---------------------------------------------------------

    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log(LogLevel.DEBUG, message, extra)

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log(LogLevel.INFO, message, extra)

    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None):
        self._log(LogLevel.WARNING, message, extra)

    def error(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exception: Optional[BaseException] = None,
    ):
        self._log(LogLevel.ERROR, message, extra, exception)

    def critical(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exception: Optional[BaseException] = None,
    ):
        self._log(LogLevel.CRITICAL, message, extra, exception)

    def for_filing(self, filing_id: str) -> 'PipelineLogger':
        """A child logger that tags every line with ``filing_id``."""
        child = PipelineLogger.__new__(PipelineLogger)
        child.__dict__.update(self.__dict__)
        child.filing_id = filing_id
        return child

    def close(self) -> None:
        """Close the dedicated logging connection, if one was opened."""
        with self._log_lock:
            if self._log_conn is not None:
                try:
                    self._log_conn.close()
                except Exception:  # noqa: BLE001 - closing must never raise
                    pass
                self._log_conn = None

    # -- internals ----------------------------------------------------------

    def _log(
        self,
        level: LogLevel,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exception: Optional[BaseException] = None,
    ):
        # stdout first: it must succeed even if the database is unreachable.
        getattr(self.logger, level.value)(
            _with_context(message, extra), exc_info=exception
        )

        if not self._should_persist(level):
            return

        try:
            self._persist(level, message, extra, exception)
        except Exception as exc:  # noqa: BLE001 - logging must never break the pipeline
            if self._persist_disabled_reason is None:
                self._persist_disabled_reason = str(exc)
                self.logger.warning(
                    "Database logging disabled for this run: %s", exc
                )
            self.persist = False

    def _should_persist(self, level: LogLevel) -> bool:
        if not self.persist or not self._dsn:
            return False
        return self._PERSIST_ORDER[level] >= self._PERSIST_ORDER[self.PERSIST_FROM]

    def _persist(
        self,
        level: LogLevel,
        message: str,
        extra: Optional[Dict[str, Any]],
        exception: Optional[BaseException],
    ) -> None:
        # Imported lazily: pipeline.db pulls in psycopg2, and stdout-only
        # logging should work in environments without it.
        from ..db import ProcessingLogRecord, ProcessingLogRepository, connect

        metadata: Dict[str, Any] = dict(extra or {})
        if exception is not None:
            metadata['exception'] = str(exception)
            metadata['exception_type'] = type(exception).__name__

        filing_id = metadata.pop('filing_id', None) or self.filing_id

        with self._log_lock:
            if self._log_conn is None or self._log_conn.closed:
                # autocommit: a log line is its own unit of work and must never
                # hold a transaction open across pipeline statements.
                self._log_conn = connect(
                    self._dsn,
                    autocommit=True,
                    application_name='10kay-pipeline-logs',
                )

            ProcessingLogRepository(self._log_conn).write(
                ProcessingLogRecord(
                    step=self.step,
                    level=level.value,
                    message=message[:8000],
                    filing_id=filing_id,
                    metadata=metadata or None,
                )
            )


def _dsn_from_connection(conn) -> Optional[str]:
    """
    Recover a DSN from an existing psycopg2 connection.

    Lets every existing ``PipelineLogger(step, db_connection=conn)`` call site
    keep working while the log writes move to their own connection.
    """
    if conn is None:
        return None
    try:
        dsn = getattr(conn, 'dsn', None)
        if dsn:
            return dsn
    except Exception:  # noqa: BLE001 - a closed connection must not break logging
        pass

    import os
    return os.getenv('DATABASE_URL')


def _with_context(message: str, extra: Optional[Dict[str, Any]]) -> str:
    """
    Append context to the stdout line.

    The previous code passed ``extra=`` straight to the stdlib logger, where
    reserved keys such as ``message``, ``module`` or ``filename`` raise
    ``KeyError: Attempt to overwrite 'x' in LogRecord`` — so a well-meaning
    ``extra={'filename': ...}`` could crash the pipeline from a log call.
    """
    if not extra:
        return message
    context = ' '.join(f"{key}={value!r}" for key, value in extra.items())
    return f"{message} | {context}"


def setup_root_logger(level: str = 'INFO') -> logging.Logger:
    """
    Configure the root logger. Returns it, so callers can attach handlers.

    ``force=True`` makes repeat calls idempotent — scripts that call this and
    then import a module that also configures logging used to end up printing
    every line twice.
    """
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
    return logging.getLogger()
