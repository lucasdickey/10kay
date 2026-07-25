"""
Database error taxonomy for the 10KAY pipeline.

Callers should be able to tell *why* a write failed without string-matching on
psycopg2 messages:

- ``TransientDatabaseError`` -> safe to retry (connection dropped, deadlock,
  serialization failure). The retry helpers in ``connection.py`` act on this.
- ``IntegrityError``         -> the data violated a constraint. Retrying the
  identical statement will fail identically; the caller must change the data.
- ``RecordNotFound``         -> a required row (company, filing, content) is
  missing. Distinct from "the query failed".
- ``DatabaseError``          -> everything else.
"""


class DatabaseError(Exception):
    """Base class for all database failures raised by the pipeline."""


class TransientDatabaseError(DatabaseError):
    """A failure that is expected to succeed if retried."""


class IntegrityError(DatabaseError):
    """A constraint violation: unique, foreign key, not-null, or check."""


class RecordNotFound(DatabaseError):
    """A row required to complete the operation does not exist."""
