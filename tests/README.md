# Tests

Two suites, split by what they need to run.

## `test_synthesis.py` — no dependencies

Covers `pipeline/analyzers/synthesis.py`: JSON extraction, truncation repair,
and field coercion. No database, no AWS, no network — it loads `synthesis.py`
directly by path so it runs even without `boto3` installed.

```bash
python3 tests/test_synthesis.py          # standalone runner
python3 -m pytest tests/test_synthesis.py -q
```

## `test_repositories.py` — needs PostgreSQL

Covers `pipeline/db/`: transaction and savepoint semantics, idempotent upserts,
the two unique keys on `filings`, slug disambiguation, batch isolation. These
assert *PostgreSQL* behaviour, so they need a real server; mocks would prove
nothing.

Exits 0 with a skip message when `TEST_DATABASE_URL` is unset, so CI without a
database stays green rather than red for the wrong reason.

```bash
createdb tenkay_test
for m in migrations/*.sql; do psql tenkay_test -f "$m"; done

TEST_DATABASE_URL=postgresql://localhost/tenkay_test python3 tests/test_repositories.py
```

Migration order matters — `010_data_integrity.sql` creates the unique indexes the
upserts target. Applying it more than once is safe.

## Both

```bash
python3 tests/run_all.py
```
