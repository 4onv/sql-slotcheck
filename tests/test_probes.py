from contextlib import closing
import sqlite3
import unittest

from sql_slotcheck.probes import PROBES, from_cursor


class ProbeTests(unittest.TestCase):
    def test_probe_expectations_run_against_sqlite(self):
        self.assertEqual(len({probe.id for probe in PROBES}), len(PROBES))
        with closing(sqlite3.connect(":memory:")) as db:
            for probe in PROBES:
                with self.subTest(probe=probe.id), closing(db.execute(probe.sql)) as cursor:
                    capture = from_cursor(cursor)
                    self.assertEqual(capture["columns"], list(probe.columns))
                    self.assertEqual(capture["rows"], [list(row) for row in probe.rows])

    def test_sqlite_row_factory_keeps_both_ordinal_values(self):
        with closing(sqlite3.connect(":memory:")) as db:
            db.row_factory = sqlite3.Row
            with closing(db.execute("SELECT 3 AS k, 5 AS k")) as cursor:
                self.assertEqual(from_cursor(cursor), {"columns": ["k", "k"], "rows": [[3, 5]]})

    def test_mapping_conversion_is_rejected_without_echoing_data(self):
        with closing(sqlite3.connect(":memory:")) as db:
            db.row_factory = lambda cursor, row: {column[0]: value for column, value in zip(cursor.description, row)}
            with closing(db.execute("SELECT 'private-sample' AS k, 5 AS k")) as cursor:
                with self.assertRaisesRegex(ValueError, "positional rows") as error:
                    from_cursor(cursor)
        self.assertNotIn("private-sample", str(error.exception))

    def test_empty_result_preserves_duplicate_schema(self):
        with closing(sqlite3.connect(":memory:")) as db:
            with closing(db.execute("SELECT 3 AS k, 5 AS k WHERE 0")) as cursor:
                self.assertEqual(from_cursor(cursor), {"columns": ["k", "k"], "rows": []})

    def test_short_batches_are_consumed_through_end(self):
        class Cursor:
            description = (("n",),)

            def __init__(self):
                self.batches = iter([[(1,)], [(2,)], []])

            def fetchmany(self, size):
                return next(self.batches)

        self.assertEqual(from_cursor(Cursor())["rows"], [[1], [2]])

    def test_result_size_limits_error_instead_of_truncating(self):
        with closing(sqlite3.connect(":memory:")) as db:
            series = "WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < ?) SELECT i FROM n"
            with closing(db.execute(series, (256,))) as cursor:
                self.assertEqual(len(from_cursor(cursor)["rows"]), 256)
            with closing(db.execute(series, (257,))) as cursor:
                with self.assertRaisesRegex(ValueError, "256-row"):
                    from_cursor(cursor)
            with closing(db.execute("SELECT " + ", ".join(["1"] * 129))) as cursor:
                with self.assertRaisesRegex(ValueError, "128 columns"):
                    from_cursor(cursor)

    def test_demo_exposes_conversion_loss_and_positional_preservation(self):
        from sql_slotcheck.demo import run_demo

        demo = run_demo()
        self.assertTrue(demo["synthetic"])
        self.assertEqual(demo["broken"]["status"], "fail")
        self.assertEqual(demo["positional"]["status"], "pass")
        broken = {probe["id"]: probe for probe in demo["broken"]["probes"]}
        self.assertEqual(broken["duplicate_join"]["status"], "fail")
        self.assertEqual(broken["empty_duplicate"]["status"], "pass")
