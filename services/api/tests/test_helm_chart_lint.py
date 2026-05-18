from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from lint_helm_chart import DEFAULT_CHART_DIR, lint_chart  # noqa: E402


class HelmChartLintTest(unittest.TestCase):
    def test_current_chart_passes_static_lint(self) -> None:
        self.assertEqual([], lint_chart(DEFAULT_CHART_DIR))

    def test_missing_required_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            chart_dir = Path(tmp) / "chart"
            shutil.copytree(DEFAULT_CHART_DIR, chart_dir)
            (chart_dir / "templates" / "api-service.yaml").unlink()

            issues = lint_chart(chart_dir)

        self.assertIn("missing required chart file: templates/api-service.yaml", issues)

    def test_unbalanced_template_delimiters_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            chart_dir = Path(tmp) / "chart"
            shutil.copytree(DEFAULT_CHART_DIR, chart_dir)
            deployment = chart_dir / "templates" / "api-deployment.yaml"
            deployment.write_text(
                deployment.read_text(encoding="utf-8") + "\nmetadata: {{ broken\n",
                encoding="utf-8",
            )

            issues = lint_chart(chart_dir)

        self.assertTrue(
            any("api-deployment.yaml has unbalanced Helm delimiters" in issue for issue in issues),
            issues,
        )


if __name__ == "__main__":
    unittest.main()
