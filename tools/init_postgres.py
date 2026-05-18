"""Apply the PostgreSQL schema to a fresh database.

Convenience wrapper around ``psql -f postgresql_schema.sql`` for environments
that already have ``psycopg`` installed (where pulling in libpq's CLI is
inconvenient — typical for our Python-only container images).

Usage::

    python tools/init_postgres.py \
        --dsn postgresql://voting:voting@127.0.0.1:5432/voting

Behaviour:
- The script reads ``services/api/internet_voting_system/sql/postgresql_schema.sql``
  and executes it as one statement batch inside autocommit mode.
- It is idempotent — the DDL uses ``CREATE TABLE IF NOT EXISTS`` /
  ``CREATE INDEX IF NOT EXISTS`` so re-running on an existing schema is safe.
- ``--drop`` first runs ``DROP SCHEMA IF EXISTS voting CASCADE``, then
  re-applies the schema. Useful for tests and ephemeral environments only;
  it deletes every voting record, so guard it carefully in production.

Exit codes:
- 0: schema applied
- 1: psycopg missing or connection failed
- 2: schema apply error
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCHEMA_FILE = (
    Path(__file__).resolve().parents[1]
    / "services"
    / "api"
    / "internet_voting_system"
    / "sql"
    / "postgresql_schema.sql"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dsn",
        required=True,
        help="PostgreSQL DSN, e.g. postgresql://voting:voting@host:5432/voting",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="DROP SCHEMA IF EXISTS voting CASCADE before applying. DESTRUCTIVE.",
    )
    args = parser.parse_args()

    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError:
        print("psycopg is not installed. Run: pip install 'psycopg[binary]>=3.1'", file=sys.stderr)
        return 1

    if not SCHEMA_FILE.exists():
        print(f"schema file not found: {SCHEMA_FILE}", file=sys.stderr)
        return 2

    sql = SCHEMA_FILE.read_text(encoding="utf-8")

    try:
        with psycopg.connect(args.dsn, autocommit=True) as conn:
            with conn.cursor() as cur:
                if args.drop:
                    print("DROP SCHEMA IF EXISTS voting CASCADE...", file=sys.stderr)
                    cur.execute("DROP SCHEMA IF EXISTS voting CASCADE")
                print(f"Applying schema from {SCHEMA_FILE.name}...", file=sys.stderr)
                cur.execute(sql)
    except psycopg.Error as exc:
        print(f"Schema apply failed: {exc}", file=sys.stderr)
        return 2

    print("Schema applied.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
