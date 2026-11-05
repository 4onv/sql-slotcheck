# SQL SlotCheck v0.1.0

Run six synthetic SQL projections through a connector and check whether its result conversion preserved every position. The included SQLite demo compares a lossy adapter with one that preserves the original cells. Use the Python callback API for a live adapter, or the manifest and JSON checker for another language.

Install the attached universal Python 3 wheel with Python 3.10+.

```sh
python -m pip install --no-deps https://github.com/4onv/sql-slotcheck/releases/download/v0.1.0/sql_slotcheck-0.1.0-py3-none-any.whl
sql-slotcheck demo
```

SQLite is the live backend exercised in v0.1.0. Default checks accept column renames if values keep their positions. Use `--exact-labels` to require identical names. SHA256SUMS contains the wheel checksum.
