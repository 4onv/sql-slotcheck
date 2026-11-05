# SQL SlotCheck

**Can your SQL adapter return both values when two columns are named `id`?**

A join can return two distinct values under the same label. A dictionary keyed by that label can silently discard one of them. SQL SlotCheck runs six synthetic queries through your adapter and checks each value by position, including column metadata for a result with zero rows.

In the synthetic join probe, the first two columns are both named `id`. SQL returns `101, 202`. The lossy adapter returns `202, 202`. SlotCheck flags row 1, column 1 and points to column 2 as a possible source of the repeated value.

[![CI](https://github.com/4onv/sql-slotcheck/actions/workflows/ci.yml/badge.svg)](https://github.com/4onv/sql-slotcheck/actions/workflows/ci.yml)

## Try the SQLite demo

With Python 3.10 or newer, run the demo directly from a checkout.

```sh
git clone https://github.com/4onv/sql-slotcheck.git
cd sql-slotcheck
python -m sql_slotcheck demo
```

The demo executes identical queries through two adapters on a real in-memory SQLite database. All inputs are synthetic. The first adapter reads cells by name and repeats values when names collide. The second reads by position and passes all six probes. Each finding gives a probe ID and, where applicable, a one-based row and column position.

To use the CLI or import the package from another project, install the release wheel.

```sh
python -m pip install --no-deps https://github.com/4onv/sql-slotcheck/releases/download/v0.1.0/sql_slotcheck-0.1.0-py3-none-any.whl
sql-slotcheck demo
```

## Check your connector

Pass a callback that sends the supplied SQL through the **same result conversion your application uses**. Return ordered column labels and positional rows from its final output.

```python
from sql_slotcheck import run_suite

def execute(sql):
    frame = my_connector.execute(sql)  # Your application connector
    return {
        "columns": list(frame.columns),
        "rows": [list(row) for row in frame.itertuples(index=False, name=None)],
    }

report = run_suite(execute)
assert report["status"] == "pass", report
```

For a raw DB-API cursor, use `from_cursor(cursor)` after executing the supplied query. Testing a downstream serializer requires routing the probe through that serializer before collecting results. The [runnable SQLite example](examples/adapter.py) shows the callback interface.

## Use another language

1. Run `sql-slotcheck spec > probes.json`. The versioned manifest includes SQL, ordered labels and expected synthetic rows.
2. Execute each query through your own adapter. Save its **observed** results by probe ID using the [capture format](docs/format.md).
3. Run `sql-slotcheck check capture.json --json` in CI. Add `--exact-labels` if your connector promises to preserve column names exactly.

The default accepts renamed labels when the column count, row count and values at every position agree. A mismatch can identify another position whose expected value matches the observed cell. That gives you a place to inspect the conversion. The report omits observed cell contents.

Exit 0 means all probes passed. Exit 1 means the suite found a mismatch, a missing probe or an execution error. Exit 2 means the command could not evaluate its input. A successful `demo` exits 0 when it demonstrates both expected outcomes.

## Coverage

| Probe | Conversion error it can expose |
| --- | --- |
| Duplicate-label join | One side of a join overwrites the other |
| Repeated label with NULL | A non-null cell becomes null or replaces it |
| Existing suffix | A generated label collides with a real column |
| Quoted case variants | Case folding merges distinct labels |
| Empty projection | Column metadata disappears when zero rows return |
| Ordered rows | A row reordering or repeated value changes its position |

SQLite is the live integration tested in this release. Other engines can run the manifest when they support its SQL. A connector that intentionally rejects duplicate names will produce an execution-error finding. Passing describes these six projections through the adapter you supplied. Production queries, other data types and concurrent workloads need their own coverage.

Read the [November 4 research](docs/research-2026-11-04.md) for the reported connector bug and the alternatives we considered. The package has zero runtime dependencies and an [MIT license](LICENSE).
