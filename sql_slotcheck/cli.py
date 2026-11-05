"""Command-line entry points for probe manifests, saved results, and the demo."""

import argparse
import json
import sys

from . import PROBES, CaptureError, __version__, evaluate_capture
from .demo import run_demo

MAX_CAPTURE_BYTES = 2 * 1024 * 1024


def _unique_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("Capture contains a repeated JSON key.")
        obj[key] = value
    return obj


def _reject_constant(_):
    raise ValueError("Capture contains a non-finite JSON number.")


def _read_capture(name):
    if name == "-":
        payload = sys.stdin.buffer.read(MAX_CAPTURE_BYTES + 1)
    else:
        with open(name, "rb") as stream:
            payload = stream.read(MAX_CAPTURE_BYTES + 1)
    if len(payload) > MAX_CAPTURE_BYTES:
        raise ValueError("Capture exceeds the 2 MiB limit.")
    return json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_keys,
                      parse_constant=_reject_constant)


def _manifest():
    return {"version": 1, "synthetic": True, "probes": [
        {"id": p.id, "sql": p.sql, "columns": list(p.columns),
         "rows": [list(row) for row in p.rows]} for p in PROBES
    ]}


def _format(report):
    lines = [f"{report['status'].upper()}  {report['summary']['passed']}/{report['summary']['total']} probes passed"]
    for probe in report["probes"]:
        lines.append(f"  {probe['status'].upper():4}  {probe['id']}")
        for finding in probe["findings"][:8]:
            if finding["code"] == "value-mismatch":
                detail = f"row {finding['row']}, column {finding['column']} has the wrong value"
                if "possibleSourceColumn" in finding:
                    detail += f" (matches expected column {finding['possibleSourceColumn']})"
                lines.append(f"        {detail}")
            else:
                fields = ", ".join(f"{k}={v}" for k, v in finding.items() if k != "code")
                lines.append(f"        {finding['code']}" + (f" ({fields})" if fields else ""))
        if probe.get("labelChanges"):
            lines.append("        Renamed labels at columns " + ", ".join(map(str, probe["labelChanges"])))
        if len(probe["findings"]) > 8:
            lines.append("        Additional findings in JSON output.")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="sql-slotcheck",
                                     description="Test column positions through your SQL adapter.")
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("spec", help="Print the synthetic SQL probe manifest as JSON.")
    demo = commands.add_parser("demo", help="Compare two adapters on in-memory SQLite.")
    demo.add_argument("--json", action="store_true")
    check = commands.add_parser("check", help="Check a saved JSON capture.")
    check.add_argument("capture", help="Capture file or - for standard input.")
    check.add_argument("--json", action="store_true")
    check.add_argument("--exact-labels", action="store_true",
                       help="Require original column labels as well as ordinal values.")
    args = parser.parse_args(argv)
    if args.command == "spec":
        print(json.dumps(_manifest(), indent=2))
        return 0
    if args.command == "demo":
        report = run_demo()
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print("SYNTHETIC DEMO | SQLite, in memory\n\nName-based adapter")
            print(_format(report["broken"]))
            print("\nPositional adapter")
            print(_format(report["positional"]))
        return 0 if report["broken"]["status"] == "fail" and report["positional"]["status"] == "pass" else 1
    try:
        capture = _read_capture(args.capture)
        report = evaluate_capture(capture, exact_labels=args.exact_labels)
    except (OSError, UnicodeError, json.JSONDecodeError, RecursionError):
        print("sql-slotcheck: cannot read capture as a bounded UTF-8 JSON document.", file=sys.stderr)
        return 2
    except (CaptureError, ValueError) as error:
        print(f"sql-slotcheck: {error}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2) if args.json else _format(report))
    return 0 if report["status"] == "pass" else 1
