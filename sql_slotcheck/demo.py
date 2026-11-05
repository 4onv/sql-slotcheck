"""A real SQLite demonstration built entirely from synthetic literal data."""

from contextlib import closing
import sqlite3

from .engine import run_suite
from .probes import from_cursor


def run_demo() -> dict:
    """Compare a lossy name-keyed conversion with a positional conversion."""
    with closing(sqlite3.connect(":memory:")) as connection:
        def positional(sql: str) -> dict:
            with closing(connection.execute(sql)) as cursor:
                return from_cursor(cursor)

        def broken(sql: str) -> dict:
            result = positional(sql)
            columns = result["columns"]
            rows = []
            for row in result["rows"]:
                # A typical serialization mistake: the later slot silently
                # overwrites the earlier one when both have the same name.
                named = dict(zip(columns, row))
                rows.append([named[name] for name in columns])
            return {"columns": columns, "rows": rows}

        return {
            "synthetic": True,
            "broken": run_suite(broken),
            "positional": run_suite(positional),
        }
