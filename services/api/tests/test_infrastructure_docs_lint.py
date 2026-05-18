from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from lint_infrastructure_docs import lint_infrastructure_docs  # noqa: E402


class InfrastructureDocsLintTest(unittest.TestCase):
    def test_current_infrastructure_docs_pass(self) -> None:
        self.assertEqual([], lint_infrastructure_docs(ROOT))

    def test_missing_required_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp) / "repo"
            shutil.copytree(ROOT, tmp_root, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            (tmp_root / "docs" / "infrastructure" / "aws-waf-cloudfront" / "outputs.tf").unlink()

            issues = lint_infrastructure_docs(tmp_root)

        self.assertIn(
            "missing required infrastructure file: docs/infrastructure/aws-waf-cloudfront/outputs.tf",
            issues,
        )

    def test_sampled_request_logging_must_stay_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp) / "repo"
            shutil.copytree(ROOT, tmp_root, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            main_tf = tmp_root / "docs" / "infrastructure" / "aws-waf-cloudfront" / "main.tf"
            main_tf.write_text(
                main_tf.read_text(encoding="utf-8").replace(
                    "sampled_requests_enabled   = false",
                    "sampled_requests_enabled   = true",
                    1,
                ),
                encoding="utf-8",
            )

            issues = lint_infrastructure_docs(tmp_root)

        self.assertTrue(
            any("sampled_requests_enabled   = false" in issue for issue in issues),
            issues,
        )


if __name__ == "__main__":
    unittest.main()
