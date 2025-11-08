"""
Logging utilities for 10KAY pipeline

Provides structured logging with context and integration with processing_logs table.
"""
import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class LogLevel(str, Enum):
    """Log levels matching database enum"""
    DEBUG = 'debug'
    INFO = 'info'
    WARNING = 'warning'
    ERROR = 'error'
    CRITICAL = 'critical'


class PipelineLogger:
    """
    Logger that writes to both stdout and database processing_logs table

    Usage:
        logger = PipelineLogger(step='fetch_filings')
        logger.info('Starting to fetch filings')
        logger.error('Failed to fetch filing', extra={'filing_id': '123'})
    """

    def __init__(
        self,
        step: str,
        filing_id: Optional[str] = None,
        db_connection=None,
        name: Optional[str] = None
    ):
        """
        Initialize logger

        Args:
            step: Pipeline step name (e.g., 'fetch_filings', 'analyze_filing')
            filing_id: Optional filing ID for context
            db_connection: Optional database connection for persisting logs
            name: Optional logger name (defaults to step)
        """
        self.step = step
        self.filing_id = filing_id
        self.db_connection = db_connection

        # Create Python logger
        self.logger = logging.getLogger(name or step)

        # Configure handler if not already configured
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def _log(
        self,
        level: LogLevel,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None
    ):
        """Internal log method that writes to both stdout and database"""

        # Log to stdout via Python logger
        log_method = getattr(self.logger, level.value)
        log_method(message, extra=extra, exc_info=exception)

        # Log to database if connection available
        if self.db_connection:
            try:
                self._persist_to_db(level, message, extra, exception)
            except Exception as e:
                self.logger.error(f"Failed to persist log to database: {e}")

    def _persist_to_db(
        self,
        level: LogLevel,
        message: str,
        extra: Optional[Dict[str, Any]],
        exception: Optional[Exception]
    ):
        """Persist log entry to processing_logs table"""
        import json
        cursor = self.db_connection.cursor()

        # Build metadata
        metadata = extra or {}
        if exception:
            metadata['exception'] = str(exception)
            metadata['exception_type'] = type(exception).__name__

        # Insert log entry
        # Use json.dumps() to serialize dict to JSONB
        cursor.execute("""
            INSERT INTO processing_logs (step, filing_id, level, message, metadata)
            VALUES (%s, %s, %s, %s, %s)
        """, (
            self.step,
            self.filing_id,
            level.value,
            message,
            json.dumps(metadata) if metadata else None
        ))

        self.db_connection.commit()
        cursor.close()

    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log debug message"""
        self._log(LogLevel.DEBUG, message, extra)

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log info message"""
        self._log(LogLevel.INFO, message, extra)

    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log warning message"""
        self._log(LogLevel.WARNING, message, extra)

    def error(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None
    ):
        """Log error message"""
        self._log(LogLevel.ERROR, message, extra, exception)

    def critical(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None
    ):
        """Log critical message"""
        self._log(LogLevel.CRITICAL, message, extra, exception)


def setup_root_logger(level: str = 'INFO'):
    """
    Setup root logger for the entire pipeline

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
