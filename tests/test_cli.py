import json
import subprocess
import sys
import unittest


def cli(*args, stdin=None):
    return subprocess.run([sys.executable, "-m", "sql_slotcheck", *args],
                          input=stdin, text=True, capture_output=True, timeout=15)


class CliContract(unittest.TestCase):
    def test_saved_probe_round_trip_and_loss_exit_code(self):
        manifest = json.loads(cli("spec").stdout)
        self.assertTrue(manifest["synthetic"])
        results = {p["id"]: {"columns": p["columns"], "rows": p["rows"]}
                   for p in manifest["probes"]}
        capture = {"version": 1, "results": results}
        passed = cli("check", "-", "--json", stdin=json.dumps(capture))
        self.assertEqual(passed.returncode, 0, passed.stderr)
        self.assertEqual(json.loads(passed.stdout)["status"], "pass")
        del results["empty_duplicate"]
        failed = cli("check", "-", "--json", stdin=json.dumps(capture))
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertEqual(json.loads(failed.stdout)["status"], "fail")

    def test_cli_rejects_duplicate_keys_and_oversize_input(self):
        for data in ['{"version":1,"version":1,"results":{}}', ' ' * (2 * 1024 * 1024 + 1)]:
            with self.subTest(size=len(data)):
                result = cli("check", "-", "--json", stdin=data)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")

    def test_demo_is_labeled_and_shows_both_adapters(self):
        result = cli("demo", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        demo = json.loads(result.stdout)
        self.assertTrue(demo["synthetic"])
        self.assertEqual(demo["broken"]["status"], "fail")
        self.assertEqual(demo["positional"]["status"], "pass")
