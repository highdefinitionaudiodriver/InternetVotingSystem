from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(ROOT / "tools"))

from lint_openapi_privacy import lint_openapi_file


class OpenApiPrivacyLintTest(unittest.TestCase):
    def test_current_openapi_passes_privacy_lint(self) -> None:
        issues = lint_openapi_file(ROOT / "docs" / "api" / "openapi.yaml")
        self.assertEqual([], [issue.format() for issue in issues])

    def test_rejects_banned_schema_property_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "openapi.yaml"
            path.write_text(
                """
openapi: 3.1.0
components:
  schemas:
    BadRequest:
      type: object
      properties:
        mynumber:
          type: string
""".strip(),
                encoding="utf-8",
            )
            issues = lint_openapi_file(path)
        self.assertEqual(1, len(issues))
        self.assertIn("mynumber", issues[0].format())

    def test_allows_policy_text_in_descriptions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "openapi.yaml"
            path.write_text(
                """
openapi: 3.1.0
info:
  description: mynumber and 個人番号 are forbidden as schema fields.
components:
  schemas:
    SafeRequest:
      type: object
      properties:
        certificate_serial:
          type: string
""".strip(),
                encoding="utf-8",
            )
            issues = lint_openapi_file(path)
        self.assertEqual([], [issue.format() for issue in issues])


if __name__ == "__main__":
    unittest.main()
