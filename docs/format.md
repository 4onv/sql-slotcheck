# Capturing a connector result

Export the version-1 manifest with `sql-slotcheck spec`. It contains six synthetic probes. Pass each probe's SQL through the component you want to test, retaining column order, duplicate labels, row order and nulls. Preserve the output of that component as observed. A second query through a different cursor would test a different path.

## Version 1

This fragment records the expected positional result for the synthetic join probe. A full capture contains all probe IDs.

```json
{
  "version": 1,
  "results": {
    "duplicate_join": {
      "columns": ["id", "id", "code", "code"],
      "rows": [[101, 202, "north", "south"]]
    }
  }
}
```

Use the current manifest for exact probe shapes and expected values. If the connector throws while executing a probe, record `{"error":true}` for that ID. For an empty projection keep the returned column labels and set `rows` to an empty array. The keys of an associative row cannot represent two occurrences of a label; use the already-converted adapter's ordered labels and values so width or value loss is observable.

Compare a file or pipe a capture from another process.

```sh
sql-slotcheck check capture.json --json
sql-slotcheck check - --exact-labels --json < capture.json
```

The report contains a verdict per probe, findings and summary counts. Row and column positions start at 1. A possible source column identifies matching synthetic evidence for a wrong cell. Multiple possible matches leave that attribution unresolved. Label changes are observable even when the chosen policy accepts them.

For an empty result the default compares column count. Use `--exact-labels` to check each label too. Cell checks compare JSON types as well as values, so a string `"101"`, an integer `101`, and a float `101.0` are distinct.

## Inputs and limits

The CLI accepts UTF-8 JSON documents up to 2 MiB. Version 1 uses arrays for labels and rows, JSON scalar cells and unique object keys. The evaluator limits a result to 128 columns and 256 rows and a string to 4,096 characters. Reports retain bounded diagnostic details. Only synthetic probes belong in these captures.

SQL runs in the caller's callback. CLI `check` reads an existing capture. The demonstration uses SQLite's in-memory database, creates no files and requires no service credentials. Result values or private exception details stay out of findings. The report describes observations at the captured layer. It cannot locate the exact operation responsible for a changed cell.
