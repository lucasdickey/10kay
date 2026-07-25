#!/usr/bin/env python3
"""
Run every test suite and report a combined result.

The database suite skips itself when TEST_DATABASE_URL is unset, so this is safe
to run anywhere:

    python3 tests/run_all.py
    TEST_DATABASE_URL=postgresql://localhost/tenkay_test python3 tests/run_all.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = ['test_synthesis.py', 'test_repositories.py']


def main() -> int:
    failed = []

    for suite in SUITES:
        print(f"\n{'=' * 70}\n{suite}\n{'=' * 70}")
        result = subprocess.run(
            [sys.executable, os.path.join(HERE, suite)],
            cwd=os.path.dirname(HERE),
        )
        if result.returncode != 0:
            failed.append(suite)

    print(f"\n{'=' * 70}")
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1

    if not os.getenv('TEST_DATABASE_URL'):
        print("All suites passed (database tests skipped - set TEST_DATABASE_URL)")
    else:
        print("All suites passed")
    return 0


if __name__ == '__main__':
    sys.exit(main())
