"""Online backup of the SQLite voting database.

Uses SQLite's built-in ``Connection.backup()`` API so the dump is consistent
even while the API process is actively writing. The output file is itself a
valid SQLite database that can be opened with `--storage sqlite --sqlite-path`.

Usage::

    python tools/backup_sqlite.py \
        --source services/api/voting.sqlite3 \
        --dest backups/voting-2026-05-18T120000Z.sqlite3

Behaviour:
- Source must exist; dest's parent directory is created if needed.
- The script uses ``sqlite3.connect()`` with a separate read-only URI handle
  for the source so the running API's write transactions are not blocked.
- After completion the destination file is opened in read-only mode and a
  quick integrity check is run; any failure exits non-zero.
- Pair with cron or systemd timers for routine offsite copies.

Exit codes:
- 0: backup OK
- 1: source missing or unreadable
- 2: backup or integrity check failed
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--dest", required=True, type=Path)
    parser.add_argument(
        "--pages-per-step",
        type=int,
        default=500,
        help="Pages copied per backup step. Tune for I/O smoothing on busy hosts.",
    )
    args = parser.parse_args()

    if not args.source.exists():
        print(f"source not found: {args.source}", file=sys.stderr)
        return 1

    args.dest.parent.mkdir(parents=True, exist_ok=True)
    # Read-only URI handle on the source — avoids contending with the API.
    src_uri = f"file:{args.source}?mode=ro"
    try:
        with sqlite3.connect(src_uri, uri=True) as src, sqlite3.connect(args.dest) as dst:
            src.backup(dst, pages=args.pages_per_step)
    except sqlite3.Error as exc:
        print(f"backup failed: {exc}", file=sys.stderr)
        return 2

    # Integrity check on the dest file.
    try:
        with sqlite3.connect(f"file:{args.dest}?mode=ro", uri=True) as check:
            result = check.execute("PRAGMA integrity_check").fetchone()
            if result is None or result[0] != "ok":
                print(f"integrity check failed: {result!r}", file=sys.stderr)
                return 2
    except sqlite3.Error as exc:
        print(f"integrity check raised: {exc}", file=sys.stderr)
        return 2

    print(f"Backed up {args.source} -> {args.dest} (integrity_check: ok)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
