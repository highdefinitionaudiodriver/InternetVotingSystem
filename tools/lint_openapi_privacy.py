from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


BANNED_FIELD_NAMES = {
    "mynumber",
    "my_number",
    "individual_number",
    "individualnumber",
    "personal_number",
    "personalnumber",
    "個人番号",
}

KEY_PATTERN = re.compile(r"^\s*(?:-\s*)?(?P<key>[A-Za-z0-9_\-\u3040-\u30ff\u3400-\u9fff]+)\s*:")
NAME_PATTERN = re.compile(r"^\s*-\s*name\s*:\s*(?P<name>[A-Za-z0-9_\-\u3040-\u30ff\u3400-\u9fff]+)\s*(?:#.*)?$")


@dataclass(frozen=True)
class LintIssue:
    path: Path
    line: int
    value: str
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.message}: {self.value}"


def normalize(value: str) -> str:
    return value.strip().strip("\"'`").replace("-", "_").lower()


def is_banned_name(value: str) -> bool:
    normalized = normalize(value)
    return normalized in BANNED_FIELD_NAMES


def lint_openapi_file(path: Path) -> list[LintIssue]:
    issues: list[LintIssue] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        name_match = NAME_PATTERN.match(line)
        if name_match and is_banned_name(name_match.group("name")):
            issues.append(
                LintIssue(
                    path=path,
                    line=line_number,
                    value=name_match.group("name"),
                    message="banned OpenAPI parameter name",
                )
            )
            continue

        key_match = KEY_PATTERN.match(line)
        if not key_match:
            continue
        key = key_match.group("key")
        if key in {"description", "summary", "title"}:
            continue
        if is_banned_name(key):
            issues.append(
                LintIssue(
                    path=path,
                    line=line_number,
                    value=key,
                    message="banned OpenAPI field/schema key",
                )
            )
    return issues


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reject OpenAPI field, schema, and parameter names that suggest collecting My Number."
    )
    parser.add_argument("paths", nargs="*", default=["docs/api/openapi.yaml"])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    issues: list[LintIssue] = []
    for raw_path in args.paths:
        path = Path(raw_path)
        if not path.exists():
            raise SystemExit(f"{path}: file not found")
        issues.extend(lint_openapi_file(path))

    if issues:
        for issue in issues:
            print(issue.format())
        raise SystemExit(1)
    print("OpenAPI privacy lint passed")


if __name__ == "__main__":
    main()
