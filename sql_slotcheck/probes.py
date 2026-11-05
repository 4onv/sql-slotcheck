"""Synthetic SQL projections and a DB-API cursor adapter for SlotCheck."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from ._validation import MAX_COLUMNS, MAX_ROWS, check_cell, check_label


Scalar = str | int | float | bool | None


@dataclass(frozen=True)
class Probe:
    """Expected output is specified by column position, starting at the left."""

    id: str
    sql: str
    columns: tuple[str, ...]
    rows: tuple[tuple[Scalar, ...], ...]


PROBES = (
    Probe(
        "duplicate_join",
        """SELECT a.id, b.id, a.code, b.code
FROM (SELECT 101 AS id, 'north' AS code) AS a
CROSS JOIN (SELECT 202 AS id, 'south' AS code) AS b""",
        ("id", "id", "code", "code"),
        ((101, 202, "north", "south"),),
    ),
    Probe(
        "null_duplicate",
        "SELECT NULL AS state, 'ready' AS state",
        ("state", "state"),
        ((None, "ready"),),
    ),
    Probe(
        "suffix_collision",
        "SELECT 13 AS qty, 17 AS qty__2, 19 AS qty",
        ("qty", "qty__2", "qty"),
        ((13, 17, 19),),
    ),
    Probe(
        "case_alias",
        "SELECT 'small' AS \"tag\", 'capital' AS \"TAG\"",
        ("tag", "TAG"),
        (("small", "capital"),),
    ),
    Probe(
        "empty_duplicate",
        "SELECT 7 AS id, 11 AS id WHERE 1 = 0",
        ("id", "id"),
        (),
    ),
    Probe(
        "ordered_rows",
        """SELECT 2 AS seq, 81 AS mark, 'second' AS mark
UNION ALL SELECT 1, 43, 'first'
ORDER BY 1""",
        ("seq", "mark", "mark"),
        ((1, 43, "first"), (2, 81, "second")),
    ),
)


def from_cursor(cursor: Any) -> dict:
    """Capture a small, already-executed DB-API result by integer position.

    Consumes the remaining rows with fetchmany. Expects unconsumed results.
    Mapping-only rows must be captured before conversion to a dict.
    """
    description = cursor.description
    if description is None or not 1 <= len(description) <= MAX_COLUMNS:
        raise ValueError(f"Expected cursor.description with 1 to {MAX_COLUMNS} columns.")
    columns = []
    text_size = 0
    for column in description:
        if isinstance(column, (str, bytes, Mapping)):
            raise ValueError("Expected DB-API column metadata entries.")
        try:
            label = column[0]
        except (TypeError, KeyError, IndexError):
            raise ValueError("Cursor metadata requires a name for each column.") from None
        text_size = check_label(label, text_size, "Cursor metadata")
        columns.append(label)

    rows = []
    while True:
        # Fetch one extra row at the boundary to distinguish a full capture
        # from an oversized one. A short nonempty batch need not be the end.
        size = min(64, MAX_ROWS + 1 - len(rows))
        batch = cursor.fetchmany(size)
        if not isinstance(batch, Sequence) or isinstance(batch, (str, bytes)) or len(batch) > size:
            raise ValueError("Cursor fetchmany must return a bounded sequence of rows.")
        if not batch:
            break
        if len(rows) + len(batch) > MAX_ROWS:
            raise ValueError(f"Result exceeds the {MAX_ROWS}-row limit.")
        for row in batch:
            if isinstance(row, (Mapping, str, bytes, bytearray, memoryview)):
                raise ValueError("Fetch positional rows before converting them to mappings.")
            try:
                if len(row) != len(columns):
                    raise ValueError("Cursor row width differs from its column metadata.")
                values = [row[position] for position in range(len(columns))]
            except (IndexError, KeyError, TypeError):
                raise ValueError("Cursor rows must support access by integer position.") from None
            for value in values:
                text_size = check_cell(value, text_size, "Cursor cell")
            rows.append(values)
    return {"columns": columns, "rows": rows}
