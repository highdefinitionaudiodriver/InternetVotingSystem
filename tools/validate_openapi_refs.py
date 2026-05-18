"""Static validator for ``$ref`` integrity in docs/api/openapi.yaml.

The official `openapi-spec-validator` package would be ideal here, but the
prototype's CI is committed to a zero-pip baseline. Instead we ship a small
checker that catches the most common drift between schemas and references:

- Every ``$ref`` value resolves to a defined component.
- Every component (under ``components.schemas`` / ``parameters`` /
  ``responses``) is referenced by at least one path or another component.
  Orphans are reported as warnings (non-fatal) so feature flags can be
  added gradually.

Pulls only ``re``/``pathlib`` from the stdlib — no YAML parsing required,
because the file's indentation and key names suffice for ``$ref`` extraction
and component definition extraction. If we later add a yaml dependency this
helper can be replaced with a real schema validator.

Exit codes: 0 ok / warnings only, 1 broken refs.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "docs" / "api" / "openapi.yaml"

REF_RE = re.compile(r'\$ref:\s*"#/components/(schemas|parameters|responses)/([A-Za-z0-9_]+)"')
# A component definition looks like:
#   <four spaces>SchemaName:
#     type: object
# at indentation depth 4 (two levels under top-level `components:`).
COMPONENT_DEF_RE = re.compile(r"^    ([A-Za-z0-9_]+):\s*$")


def _parse_components(text: str) -> dict[str, set[str]]:
    """Return mapping of section -> {component name, ...}."""
    components: dict[str, set[str]] = {"schemas": set(), "parameters": set(), "responses": set()}
    section: str | None = None
    for line in text.splitlines():
        stripped = line.rstrip()
        if stripped == "components:":
            section = None
            continue
        # Match the section header (`  schemas:`, `  parameters:`, `  responses:`)
        # at depth 2.
        if stripped.startswith("  ") and stripped.endswith(":") and not stripped.startswith("    "):
            name = stripped.strip().rstrip(":")
            if name in components:
                section = name
                continue
            # Some other 2-space key inside components (e.g. requestBodies).
            section = None
            continue
        if section is None:
            continue
        m = COMPONENT_DEF_RE.match(line)
        if m:
            components[section].add(m.group(1))
    return components


def _parse_refs(text: str) -> list[tuple[str, str]]:
    return REF_RE.findall(text)


def validate(text: str) -> tuple[list[str], list[str]]:
    components = _parse_components(text)
    refs = _parse_refs(text)
    errors: list[str] = []
    referenced: dict[str, set[str]] = {k: set() for k in components}
    for section, name in refs:
        if name not in components.get(section, set()):
            errors.append(f"broken $ref: #/components/{section}/{name}")
        else:
            referenced[section].add(name)
    warnings: list[str] = []
    for section, names in components.items():
        for name in sorted(names - referenced[section]):
            warnings.append(f"orphan component: #/components/{section}/{name}")
    return errors, warnings


def main() -> int:
    if not SPEC.exists():
        print(f"openapi spec not found: {SPEC}", file=sys.stderr)
        return 1
    text = SPEC.read_text(encoding="utf-8")
    errors, warnings = validate(text)
    for warning in warnings:
        print(f"OpenAPI spec warning: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"OpenAPI spec error: {error}", file=sys.stderr)
        return 1
    print("OpenAPI spec ref check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
