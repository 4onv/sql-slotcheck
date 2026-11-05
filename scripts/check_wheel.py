"""Install and exercise the actual wheel from an isolated environment."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv


def main():
    wheels = sorted(Path(sys.argv[1]).resolve().glob("sql_slotcheck-*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Pass a directory containing exactly one SQL SlotCheck wheel.")
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    with tempfile.TemporaryDirectory(prefix="sql-slotcheck-wheel-") as temporary:
        root = Path(temporary)
        prefix = root / "env"
        venv.EnvBuilder(with_pip=True).create(prefix)
        scripts = prefix / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        cli = scripts / ("sql-slotcheck.exe" if os.name == "nt" else "sql-slotcheck")

        def run(args, **kwargs):
            return subprocess.run(args, cwd=root, env=env, text=True, timeout=60,
                                  check=True, capture_output=True, **kwargs).stdout

        run([python, "-m", "pip", "install", "--no-index", "--no-deps", wheels[0]])
        manifest = json.loads(run([cli, "spec"]))
        version = run([cli, "--version"]).strip()
        if wheels[0].name.split("-")[1] != version:
            raise RuntimeError("Installed CLI version differs from the wheel filename.")
        capture = {"version": 1, "results": {
            p["id"]: {"columns": p["columns"], "rows": p["rows"]} for p in manifest["probes"]
        }}
        report = json.loads(run([cli, "check", "-", "--json"], input=json.dumps(capture)))
        demo = json.loads(run([cli, "demo", "--json"]))
        if (report["status"], demo["broken"]["status"], demo["positional"]["status"]) != ("pass", "fail", "pass"):
            raise RuntimeError("Installed wheel failed its capture or demo check.")
        print(f"Installed {version} offline and exercised {len(manifest['probes'])} SQL probes.")


if __name__ == "__main__":
    main()
