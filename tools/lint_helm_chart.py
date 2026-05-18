from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHART_DIR = ROOT / "deploy" / "helm" / "internet-voting-system"

REQUIRED_FILES = (
    "Chart.yaml",
    "values.yaml",
    "templates/_helpers.tpl",
    "templates/api-deployment.yaml",
    "templates/api-service.yaml",
    "templates/postgres-secret.yaml",
    "templates/sqlite-pvc.yaml",
    "templates/web-deployment.yaml",
    "templates/pdb.yaml",
)

CHART_REQUIRED_SNIPPETS = (
    "apiVersion: v2",
    "name: internet-voting-system",
    "type: application",
    "version:",
    "appVersion:",
)

VALUES_REQUIRED_SNIPPETS = (
    "backend: memory",
    "repository: ghcr.io/highdefinitionaudiodriver/internet-voting-system-api",
    "repository: ghcr.io/highdefinitionaudiodriver/internet-voting-system-web",
    "replicaCount:",
)


def lint_chart(chart_dir: Path = DEFAULT_CHART_DIR) -> list[str]:
    issues: list[str] = []

    if not chart_dir.exists():
        return [f"chart directory does not exist: {chart_dir}"]

    for relative in REQUIRED_FILES:
        if not (chart_dir / relative).is_file():
            issues.append(f"missing required chart file: {relative}")

    chart_yaml = _read_if_present(chart_dir / "Chart.yaml")
    for snippet in CHART_REQUIRED_SNIPPETS:
        if snippet not in chart_yaml:
            issues.append(f"Chart.yaml missing required snippet: {snippet}")

    values_yaml = _read_if_present(chart_dir / "values.yaml")
    for snippet in VALUES_REQUIRED_SNIPPETS:
        if snippet not in values_yaml:
            issues.append(f"values.yaml missing required snippet: {snippet}")

    for path in sorted(chart_dir.rglob("*")):
        if path.suffix not in {".yaml", ".tpl"}:
            continue
        text = _read_if_present(path)
        opens = text.count("{{")
        closes = text.count("}}")
        if opens != closes:
            issues.append(
                f"{path.relative_to(chart_dir)} has unbalanced Helm delimiters: "
                f"{opens} opening vs {closes} closing"
            )

    api_deployment = _read_if_present(chart_dir / "templates" / "api-deployment.yaml")
    if 'replicas: {{ if eq .Values.storage.backend "sqlite" }}1' not in api_deployment:
        issues.append("api-deployment.yaml must force one replica for sqlite storage")
    if "/health" not in api_deployment:
        issues.append("api-deployment.yaml must configure health probes")
    postgres_secret = _read_if_present(chart_dir / "templates" / "postgres-secret.yaml")
    if "fail" not in postgres_secret or "storage.postgres.dsn" not in postgres_secret:
        issues.append("postgres-secret.yaml must fail fast when postgres DSN is missing")

    sqlite_pvc = _read_if_present(chart_dir / "templates" / "sqlite-pvc.yaml")
    if 'eq .Values.storage.backend "sqlite"' not in sqlite_pvc:
        issues.append("sqlite-pvc.yaml must only render for sqlite storage")

    return issues


def _read_if_present(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def main() -> None:
    chart_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CHART_DIR
    issues = lint_chart(chart_dir)
    if issues:
        for issue in issues:
            print(f"Helm chart lint error: {issue}", file=sys.stderr)
        raise SystemExit(1)
    print("Helm chart static lint passed")


if __name__ == "__main__":
    main()
