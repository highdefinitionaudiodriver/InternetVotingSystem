from __future__ import annotations

import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOOL = ROOT / "tools" / "backup_sqlite.py"


class BackupSqliteToolTest(unittest.TestCase):
    """Run the backup tool as a subprocess against a synthetic source database."""

    def test_backup_creates_intact_copy(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            src = Path(tmpdir) / "src.sqlite3"
            dest = Path(tmpdir) / "backups" / "dest.sqlite3"

            with closing(sqlite3.connect(src)) as conn:
                conn.execute("CREATE TABLE ballots (id INTEGER PRIMARY KEY, payload TEXT)")
                conn.executemany(
                    "INSERT INTO ballots (payload) VALUES (?)",
                    [(f"payload-{i}",) for i in range(100)],
                )
                conn.commit()

            result = subprocess.run(
                [sys.executable, str(TOOL), "--source", str(src), "--dest", str(dest)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(dest.exists())
            # Destination must contain exactly the same rows.
            with closing(sqlite3.connect(dest)) as check:
                count = check.execute("SELECT COUNT(*) FROM ballots").fetchone()[0]
            self.assertEqual(count, 100)

    def test_missing_source_returns_exit_code_1(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            result = subprocess.run(
                [
                    sys.executable, str(TOOL),
                    "--source", str(Path(tmpdir) / "does-not-exist.sqlite3"),
                    "--dest", str(Path(tmpdir) / "dest.sqlite3"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
