from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_step(name: str, command: list[str], cwd: Path = ROOT) -> None:
    print(f"\n== {name} ==", flush=True)
    print(" ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True, stderr=subprocess.STDOUT)


def main() -> None:
    node = shutil.which("node")
    if node is None:
        raise SystemExit("node executable was not found; install Node.js or run CI for web JavaScript checks")

    run_step(
        "API unit tests",
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=ROOT / "services" / "api",
    )
    run_step("OpenAPI privacy lint", [sys.executable, "tools/lint_openapi_privacy.py"])
    run_step("Helm chart static lint", [sys.executable, "tools/lint_helm_chart.py"])
    run_step("Infrastructure docs lint", [sys.executable, "tools/lint_infrastructure_docs.py"])
    run_step("Web JavaScript syntax", [node, "--check", "client-web/main.js"])
    run_step(
        "Standalone tool syntax",
        [
            sys.executable,
            "-m",
            "py_compile",
            "tools/smoke_check.py",
            "tools/loadtest.py",
            "tools/lint_openapi_privacy.py",
            "tools/lint_helm_chart.py",
            "tools/lint_infrastructure_docs.py",
            "tools/check_all.py",
            "tools/init_postgres.py",
            "tools/backup_sqlite.py",
        ],
    )
    run_step(
        "Grafana dashboard JSON parses",
        [sys.executable, "-c", "import json,pathlib; json.loads(pathlib.Path('docs/grafana/internet-voting-system.json').read_text(encoding='utf-8'))"],
    )
    print("\nAll checks passed", flush=True)


if __name__ == "__main__":
    main()
