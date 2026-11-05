"""Run with: python -m examples.adapter (from a source checkout)."""

from contextlib import closing
import json
import sqlite3

from sql_slotcheck import from_cursor, run_suite


def main() -> int:
    # Replace the body of execute() with a call through your application adapter.
    # Hand SlotCheck the actual column labels and positional rows it returns.
    with closing(sqlite3.connect(":memory:")) as connection:
        def execute(sql: str) -> dict:
            with closing(connection.execute(sql)) as cursor:
                return from_cursor(cursor)

        report = run_suite(execute)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
