"""Compare an adapter's ordered result columns and values with fixed SQL probes."""

from __future__ import annotations

from ._validation import MAX_COLUMNS, MAX_ROWS, TYPE_NAMES, CaptureError, check_cell, check_label
from .probes import PROBES


MAX_FINDINGS = 64
_MISSING = object()


def _validate_result(result, probe_id):
    location = f"results.{probe_id}"
    if not isinstance(result, dict) or result.keys() != {"columns", "rows"}:
        raise CaptureError(f"{location} must contain exactly columns and rows, or error=true.")
    columns, rows = result["columns"], result["rows"]
    if not isinstance(columns, (list, tuple)) or len(columns) > MAX_COLUMNS:
        raise CaptureError(f"{location}.columns must be an array of at most {MAX_COLUMNS} labels.")
    if not isinstance(rows, (list, tuple)) or len(rows) > MAX_ROWS:
        raise CaptureError(f"{location}.rows must be an array of at most {MAX_ROWS} rows.")

    text_size = 0
    for column in columns:
        text_size = check_label(column, text_size, f"{location}.columns")
    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, (list, tuple)) or len(row) > MAX_COLUMNS:
            raise CaptureError(f"{location} row {row_number} must be a positional array of at most {MAX_COLUMNS} cells.")
        for column_number, value in enumerate(row, start=1):
            text_size = check_cell(value, text_size, f"{location} row {row_number}, column {column_number}")
    return columns, rows


def _same_cell(actual, expected):
    # Python otherwise equates True, 1 and 1.0.
    return type(actual) is type(expected) and actual == expected


def _single_failure(probe, code):
    return {
        "id": probe.id,
        "status": "fail",
        "findings": [{"code": code}],
        "labelChanges": [],
        "omittedFindings": 0,
    }


def _compare(probe, result, exact_labels):
    if result is _MISSING:
        return _single_failure(probe, "missing-probe")
    if isinstance(result, dict) and result.keys() == {"error"} and result["error"] is True:
        return _single_failure(probe, "executor-error")
    columns, rows = _validate_result(result, probe.id)
    findings = []
    total_findings = 0

    def note(code, **details):
        nonlocal total_findings
        total_findings += 1
        if len(findings) < MAX_FINDINGS:
            findings.append({"code": code, **details})

    expected_width = len(probe.columns)
    if len(columns) != expected_width:
        note("column-count", expected=expected_width, actual=len(columns))
    label_changes = [
        slot for slot, (expected, actual) in enumerate(zip(probe.columns, columns), start=1)
        if expected != actual
    ]
    if exact_labels:
        for slot in label_changes:
            note("label-mismatch", column=slot)
    if len(rows) != len(probe.rows):
        note("row-count", expected=len(probe.rows), actual=len(rows))

    for row_index, row in enumerate(rows):
        if len(row) != expected_width:
            note("row-width", row=row_index + 1, expected=expected_width, actual=len(row))
        if row_index >= len(probe.rows):
            continue
        expected_row = probe.rows[row_index]
        for column_index, (expected, actual) in enumerate(zip(expected_row, row)):
            if _same_cell(actual, expected):
                continue
            details = {
                "row": row_index + 1,
                "column": column_index + 1,
                "expectedType": TYPE_NAMES[type(expected)],
                "observedType": TYPE_NAMES[type(actual)],
            }
            if actual is not None:
                matches = [
                    slot for slot, candidate in enumerate(expected_row, start=1)
                    if _same_cell(candidate, actual)
                ]
                if len(matches) == 1:
                    details["possibleSourceColumn"] = matches[0]
            note("value-mismatch", **details)
    return {
        "id": probe.id,
        "status": "fail" if total_findings else "pass",
        "findings": findings,
        "labelChanges": label_changes,
        "omittedFindings": total_findings - len(findings),
    }


def _report(results):
    passed = sum(result["status"] == "pass" for result in results)
    failed = len(results) - passed
    return {
        "version": 1,
        "status": "fail" if failed else "pass",
        "probes": results,
        "summary": {"passed": passed, "failed": failed, "total": len(results)},
    }


def _check_label_option(exact_labels):
    if type(exact_labels) is not bool:
        raise CaptureError("exact_labels must be a boolean.")


def evaluate_capture(capture, *, exact_labels=False):
    """Check all catalog probes against a version-1 capture. Findings use 1-based slots."""
    _check_label_option(exact_labels)
    if not isinstance(capture, dict) or capture.keys() != {"version", "results"}:
        raise CaptureError("Capture must contain exactly version and results.")
    if type(capture["version"]) is not int or capture["version"] != 1:
        raise CaptureError("Capture version must be the integer 1.")
    results = capture["results"]
    if not isinstance(results, dict):
        raise CaptureError("results must be an object keyed by probe ID.")
    known_ids = {probe.id for probe in PROBES}
    if len(results) > len(known_ids) or any(probe_id not in known_ids for probe_id in results):
        raise CaptureError("results contains an unknown probe ID.")
    return _report([_compare(probe, results.get(probe.id, _MISSING), exact_labels) for probe in PROBES])


def run_suite(execute, *, exact_labels=False):
    """Send fixed synthetic SQL through execute(sql) and check its returned positional results."""
    _check_label_option(exact_labels)
    if not callable(execute):
        raise TypeError("execute must be a callable accepting one SQL string.")
    reports = []
    for probe in PROBES:
        try:
            result = execute(probe.sql)
        except Exception:
            # Exception messages can include SQL, credentials or row data.
            result = {"error": True}
        reports.append(_compare(probe, result, exact_labels))
    return _report(reports)
