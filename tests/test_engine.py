import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sql_slotcheck.engine import CaptureError, evaluate_capture, run_suite
from sql_slotcheck.probes import PROBES


def clean_capture():
    return {
        "version": 1,
        "results": {
            probe.id: {"columns": list(probe.columns), "rows": [list(row) for row in probe.rows]}
            for probe in PROBES
        },
    }


def checked_probe(report, probe_id):
    return next(probe for probe in report["probes"] if probe["id"] == probe_id)


class EngineTests(unittest.TestCase):
    def test_complete_ordered_capture_passes_all_probes(self):
        capture = clean_capture()
        report = evaluate_capture(capture)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["summary"], {"passed": len(PROBES), "failed": 0, "total": len(PROBES)})
        self.assertEqual([probe["id"] for probe in report["probes"]], [probe.id for probe in PROBES])

    def test_repeated_value_from_same_label_is_localized(self):
        capture = clean_capture()
        result = capture["results"]["duplicate_join"]
        columns = result["columns"]
        row = result["rows"][0]
        left, right = next(
            (left, right) for right in range(len(row)) for left in range(right)
            if columns[left] == columns[right] and row[left] != row[right] and row.count(row[left]) == 1
        )
        row[right] = row[left]
        report = evaluate_capture(capture)
        self.assertEqual(report["summary"]["failed"], 1)
        findings = checked_probe(report, "duplicate_join")["findings"]
        self.assertEqual(len(findings), 1)
        finding = findings[0]
        self.assertEqual((finding["code"], finding["row"], finding["column"]), ("value-mismatch", 1, right + 1))
        self.assertEqual(finding["possibleSourceColumn"], left + 1)

    def test_collapsed_mapping_width_and_empty_result_schema_are_visible(self):
        capture = clean_capture()
        join = capture["results"]["duplicate_join"]
        join["columns"] = list(dict.fromkeys(join["columns"]))
        join["rows"] = [row[:len(join["columns"])] for row in join["rows"]]
        capture["results"]["empty_duplicate"]["columns"] = []
        report = evaluate_capture(capture)
        self.assertEqual(report["summary"]["failed"], 2)
        self.assertIn("row-width", [item["code"] for item in checked_probe(report, "duplicate_join")["findings"]])
        empty_findings = checked_probe(report, "empty_duplicate")["findings"]
        self.assertEqual([item["code"] for item in empty_findings], ["column-count"])
        self.assertEqual(empty_findings[0]["actual"], 0)

    def test_renames_are_not_data_loss_and_exact_labels_are_optional(self):
        capture = clean_capture()
        secret_label = "sensitive alias"
        capture["results"]["duplicate_join"]["columns"][1] = secret_label
        report = evaluate_capture(capture)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(checked_probe(report, "duplicate_join")["labelChanges"], [2])
        strict_report = evaluate_capture(capture, exact_labels=True)
        self.assertEqual(checked_probe(strict_report, "duplicate_join")["findings"], [
            {"code": "label-mismatch", "column": 2},
        ])
        self.assertNotIn(secret_label, json.dumps(strict_report))

    def test_missing_and_errored_probes_fail_individually(self):
        capture = clean_capture()
        del capture["results"]["duplicate_join"]
        capture["results"]["empty_duplicate"] = {"error": True}
        report = evaluate_capture(capture)
        self.assertEqual(report["summary"]["failed"], 2)
        self.assertEqual(checked_probe(report, "duplicate_join")["findings"], [{"code": "missing-probe"}])
        self.assertEqual(checked_probe(report, "empty_duplicate")["findings"], [{"code": "executor-error"}])

    def test_types_and_ambiguous_sentinels_are_distinguished(self):
        probe = SimpleNamespace(id="boundary", columns=("a", "b", "c", "d"), rows=((1, "same", "same", None),))
        with patch("sql_slotcheck.engine.PROBES", [probe]):
            report = evaluate_capture({
                "version": 1,
                "results": {"boundary": {"columns": list(probe.columns), "rows": [[True, None, "same", "same"]]}},
            })
        findings = report["probes"][0]["findings"]
        self.assertEqual([item["column"] for item in findings], [1, 2, 4])
        self.assertEqual(findings[0]["expectedType"], "integer")
        self.assertEqual(findings[0]["observedType"], "boolean")
        self.assertTrue(all("possibleSourceColumn" not in item for item in findings))

    def test_changed_order_and_missing_rows_are_detected(self):
        capture = clean_capture()
        rows = capture["results"]["ordered_rows"]["rows"]
        self.assertGreaterEqual(len(rows), 2)
        rows.reverse()
        report = evaluate_capture(capture)
        self.assertTrue(any(f["code"] == "value-mismatch" for f in checked_probe(report, "ordered_rows")["findings"]))
        rows.clear()
        report = evaluate_capture(capture)
        self.assertEqual(checked_probe(report, "ordered_rows")["findings"][0]["code"], "row-count")

    def test_reports_and_capture_errors_exclude_observed_content(self):
        secret = "untrusted private data"
        capture = clean_capture()
        result = capture["results"]["duplicate_join"]
        result["columns"][0] = secret
        result["rows"][0][0] = secret
        report = evaluate_capture(capture, exact_labels=True)
        self.assertEqual(report["status"], "fail")
        self.assertNotIn(secret, json.dumps(report))
        result["rows"] = [{secret: secret}]
        with self.assertRaises(CaptureError) as error:
            evaluate_capture(capture)
        self.assertNotIn(secret, str(error.exception))

    def test_rejects_invalid_envelopes_instead_of_silently_truncating(self):
        samples = [
            {"version": True, "results": {}}, {"version": 1.0, "results": {}},
            {"version": 1, "results": {}, "extra": True}, {"version": 1, "results": []},
            {"version": 1, "results": {"invalid id": {}}},
        ]
        samples.extend(
            {"version": 1, "results": {"duplicate_join": invalid}}
            for invalid in [
                {"error": 1}, {"error": True, "rows": []}, {"columns": [], "rows": [[]], "extra": True},
                {"columns": [None], "rows": []}, {"columns": ["x"], "rows": [{"x": 1}]},
                {"columns": ["x"], "rows": [[{"x": 1}]]}, {"columns": ["x"], "rows": [[float("nan")]]},
                {"columns": ["x"], "rows": [[float("inf")]]}, {"columns": ["x"], "rows": [[2 ** 4096]]},
                {"columns": ["x"] * 129, "rows": []}, {"columns": [], "rows": [[]] * 257},
                {"columns": ["x"], "rows": [["s" * 4097]]},
            ]
        )
        for number, sample in enumerate(samples):
            with self.subTest(sample_number=number), self.assertRaises(CaptureError):
                evaluate_capture(sample)
        with self.assertRaises(CaptureError):
            evaluate_capture(clean_capture(), exact_labels="false")

    def test_findings_are_capped_with_exact_omission_count(self):
        capture = clean_capture()
        capture["results"]["duplicate_join"]["rows"] = [[] for _ in range(256)]
        result = checked_probe(evaluate_capture(capture), "duplicate_join")
        self.assertEqual(len(result["findings"]), 64)
        self.assertEqual(result["omittedFindings"], 257 - 64)

    def test_callback_uses_actual_sql_and_keeps_private_exception_details_out(self):
        capture = clean_capture()
        by_sql = {probe.sql: probe.id for probe in PROBES}
        calls = []

        def execute(sql):
            calls.append(sql)
            if by_sql[sql] == "duplicate_join":
                raise RuntimeError("private-connection-details")
            return capture["results"][by_sql[sql]]

        report = run_suite(execute)
        self.assertEqual(calls, [probe.sql for probe in PROBES])
        self.assertEqual(report["summary"]["failed"], 1)
        self.assertNotIn("private-connection-details", json.dumps(report))
        self.assertEqual(checked_probe(report, "duplicate_join")["findings"], [{"code": "executor-error"}])

    def test_callback_interrupts_propagate(self):
        def interrupted(sql):
            raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            run_suite(interrupted)
