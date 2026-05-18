"""PostgreSQL-backed Repository implementation.

This module implements the same :class:`Repository` protocol as
``sqlite_repository.py`` but talks to PostgreSQL through ``psycopg`` (3.x). It
is the production-recommended backend for multi-host deployments.

Status: **untested in CI**. ``psycopg`` is not pulled in as a hard dependency
of the prototype, so this module imports it lazily and raises a clear error if
the driver is missing. The schema is defined in
``services/api/internet_voting_system/sql/postgresql_schema.sql`` and the SQL
statements below are kept in 1:1 correspondence with that file.

Typical use::

    from internet_voting_system.postgres_repository import PostgresRepository
    repo = PostgresRepository(dsn="postgresql://user:pw@db:5432/voting")
    service = VotingService(repository=repo)

The repository uses ``SELECT ... FOR UPDATE`` to model the token-issuance
critical section. Combined with ``READ COMMITTED`` isolation and the unique
constraint ``UNIQUE (blind_token_hash, revote_serial)`` on ballots, double
voting is prevented at the database level even under concurrent submissions.
"""

from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from .crypto import canonical_json, sha256_hex
from .models import AuditLogEntry, Ballot, Candidate, Election, VoterStatus, utc_now
from .repository_base import _verify_chain, bucket_5_minutes


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _from_dt(value: Any) -> datetime:
    """Coerce ``timestamptz`` / ISO-string values to a UTC ``datetime``.

    ``psycopg`` returns ``datetime`` directly for timestamptz columns; tests
    that fake the driver may pass plain strings. Both are accepted.
    """
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc)


class PostgresRepository:
    """Production-grade Repository backed by PostgreSQL.

    Parameters
    ----------
    dsn:
        Standard libpq connection string (``postgresql://...``) consumed by
        ``psycopg.connect``.
    seed:
        Whether to insert the ``demo-2026`` election if the table is empty.
        Set to ``False`` in production.
    schema:
        Postgres schema to use (default ``voting``). Matches the SQL DDL.
    """

    def __init__(self, dsn: str, seed: bool = True, schema: str = "voting") -> None:
        try:
            import psycopg  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "PostgresRepository requires the 'psycopg' package. "
                "Install it with `pip install 'psycopg[binary]>=3.1'`."
            ) from exc

        self._psycopg = psycopg
        self._lock = threading.RLock()
        # autocommit=False so we can hand-craft transactions for the
        # token-issuance critical section.
        self._conn = psycopg.connect(dsn, autocommit=False)
        self._schema = schema
        with self._conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema}, public")
        self._conn.commit()
        if seed:
            with self._conn.cursor() as cur:
                cur.execute("SELECT 1 FROM elections LIMIT 1")
                exists = cur.fetchone() is not None
            if not exists:
                self.seed_demo_data()

    # ------------------------------------------------------------------
    # audit_logs accessor (mirrors the in-memory + SQLite shape)
    # ------------------------------------------------------------------
    @property
    def audit_logs(self) -> list[AuditLogEntry]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "SELECT log_id, prev_hash, log_hash, component, event_type, payload, occurred_at "
                "FROM audit_log ORDER BY log_id"
            )
            rows = cur.fetchall()
        return [
            AuditLogEntry(
                log_id=int(r[0]),
                prev_hash=str(r[1]),
                log_hash=str(r[2]),
                component=str(r[3]),
                event_type=str(r[4]),
                payload=r[5] if isinstance(r[5], dict) else json.loads(r[5]),
                occurred_at=_from_dt(r[6]),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def seed_demo_data(self) -> None:
        now = utc_now()
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO elections (election_id, title, starts_at, ends_at, voter_salt, status) "
                "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (election_id) DO NOTHING",
                (
                    "demo-2026",
                    "デモ選挙 2026",
                    now - timedelta(days=1),
                    now + timedelta(days=7),
                    secrets.token_hex(16),
                    "open",
                ),
            )
            for cid, name, party in [
                ("cand-a", "候補者A", "未来党"),
                ("cand-b", "候補者B", "市民ネット"),
                ("cand-c", "候補者C", "無所属"),
            ]:
                cur.execute(
                    "INSERT INTO candidates (election_id, candidate_id, display_name, party) "
                    "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    ("demo-2026", cid, name, party),
                )
            self._conn.commit()
        self.append_audit("system", "election_seeded", {"election_id": "demo-2026"})

    def _row_to_election(self, row: tuple[Any, ...], cur: Any) -> Election:
        election_id = str(row[0])
        cur.execute(
            "SELECT candidate_id, display_name, party FROM candidates "
            "WHERE election_id = %s ORDER BY candidate_id",
            (election_id,),
        )
        candidates = [Candidate(str(c[0]), str(c[1]), str(c[2])) for c in cur.fetchall()]
        return Election(
            election_id=election_id,
            title=str(row[1]),
            starts_at=_from_dt(row[2]),
            ends_at=_from_dt(row[3]),
            voter_salt=str(row[4]),
            candidates=candidates,
            status=str(row[5]),
        )

    def list_elections(self) -> list[Election]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "SELECT election_id, title, starts_at, ends_at, voter_salt, status "
                "FROM elections ORDER BY election_id"
            )
            rows = cur.fetchall()
            return [self._row_to_election(r, cur) for r in rows]

    def get_election(self, election_id: str) -> Election:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "SELECT election_id, title, starts_at, ends_at, voter_salt, status "
                "FROM elections WHERE election_id = %s",
                (election_id,),
            )
            row = cur.fetchone()
            if row is None:
                raise KeyError("election not found")
            return self._row_to_election(row, cur)

    def create_election(self, data: dict[str, Any]) -> Election:
        candidates = [
            Candidate(str(item["candidate_id"]), str(item["display_name"]), str(item.get("party", "")))
            for item in data["candidates"]
        ]
        if len({c.candidate_id for c in candidates}) != len(candidates):
            raise ValueError("candidate_id must be unique")
        starts_at = _from_dt(str(data["starts_at"]))
        ends_at = _from_dt(str(data["ends_at"]))
        if starts_at >= ends_at:
            raise ValueError("starts_at must be earlier than ends_at")
        election_id = str(data["election_id"])
        status = str(data.get("status", "open"))
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT 1 FROM elections WHERE election_id = %s", (election_id,))
            if cur.fetchone() is not None:
                raise ValueError("election already exists")
            cur.execute(
                "INSERT INTO elections (election_id, title, starts_at, ends_at, voter_salt, status) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (election_id, str(data["title"]), starts_at, ends_at, secrets.token_hex(16), status),
            )
            for c in candidates:
                cur.execute(
                    "INSERT INTO candidates (election_id, candidate_id, display_name, party) VALUES (%s, %s, %s, %s)",
                    (election_id, c.candidate_id, c.display_name, c.party),
                )
            self._conn.commit()
        self.append_audit("admin", "election_created", {"election_id": election_id})
        return self.get_election(election_id)

    def set_election_status(self, election_id: str, status: str) -> Election:
        if status not in ("open", "closed"):
            raise ValueError("status must be 'open' or 'closed'")
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "UPDATE elections SET status = %s WHERE election_id = %s",
                (status, election_id),
            )
            if cur.rowcount == 0:
                self._conn.rollback()
                raise KeyError("election not found")
            self._conn.commit()
        return self.get_election(election_id)

    # ------------------------------------------------------------------
    # Voter status
    # ------------------------------------------------------------------
    def get_or_create_voter_status(self, election_id: str, voter_hash: str) -> VoterStatus:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "SELECT voter_hash, election_id, token_issued, token_issued_at, revote_count, last_issued_token_hash "
                "FROM voter_status WHERE election_id = %s AND voter_hash = %s",
                (election_id, voter_hash),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "INSERT INTO voter_status (voter_hash, election_id) VALUES (%s, %s)",
                    (voter_hash, election_id),
                )
                self._conn.commit()
                return VoterStatus(voter_hash=voter_hash, election_id=election_id)
            return VoterStatus(
                voter_hash=str(row[0]),
                election_id=str(row[1]),
                token_issued=bool(row[2]),
                token_issued_at=_from_dt(row[3]) if row[3] else None,
                revote_count=int(row[4]),
                last_issued_token_hash=row[5],
            )

    def mark_token_issued(self, election_id: str, voter_hash: str, token_hash: str) -> VoterStatus:
        with self._lock, self._conn.cursor() as cur:
            # SELECT ... FOR UPDATE acquires a row lock so concurrent issuers
            # serialise on the voter row. If the row does not yet exist we
            # insert first, then re-select with the lock held.
            cur.execute(
                "SELECT 1 FROM voter_status WHERE election_id = %s AND voter_hash = %s",
                (election_id, voter_hash),
            )
            if cur.fetchone() is None:
                cur.execute(
                    "INSERT INTO voter_status (voter_hash, election_id) VALUES (%s, %s)",
                    (voter_hash, election_id),
                )
            cur.execute(
                "SELECT 1 FROM voter_status WHERE election_id = %s AND voter_hash = %s FOR UPDATE",
                (election_id, voter_hash),
            )
            cur.execute(
                "UPDATE voter_status SET token_issued = TRUE, token_issued_at = now(), "
                "revote_count = revote_count + 1, last_issued_token_hash = %s "
                "WHERE election_id = %s AND voter_hash = %s",
                (token_hash, election_id, voter_hash),
            )
            self._conn.commit()
        status = self.get_or_create_voter_status(election_id, voter_hash)
        self.append_audit(
            "blind-signer",
            "token_issued",
            {"election_id": election_id, "token_hash": token_hash, "revote_count": status.revote_count},
        )
        return status

    # ------------------------------------------------------------------
    # Ballots
    # ------------------------------------------------------------------
    def next_ballot_serial(self, token_hash: str) -> int:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM ballot WHERE blind_token_hash = %s", (token_hash,))
            n = int(cur.fetchone()[0])
            return n + 1

    def _row_to_ballot(self, row: tuple[Any, ...]) -> Ballot:
        encrypted_vote = row[3] if isinstance(row[3], dict) else json.loads(row[3])
        return Ballot(
            ballot_id=str(row[0]),
            election_id=str(row[1]),
            blind_token_hash=str(row[2]),
            encrypted_vote=encrypted_vote,
            zk_proof=str(row[4]),
            received_at_bucket=_from_dt(row[5]),
            sequence_in_bucket=int(row[6]),
            revote_serial=int(row[7]),
            receipt_hash=str(row[8]),
            accepted_candidate_id=str(row[9]),
        )

    def store_ballot(
        self,
        ballot_id: str,
        election_id: str,
        token_hash: str,
        encrypted_vote: dict[str, str],
        zk_proof: str,
        receipt_hash: str,
        accepted_candidate_id: str,
    ) -> Ballot:
        with self._lock, self._conn.cursor() as cur:
            now_bucket = bucket_5_minutes(utc_now())
            cur.execute(
                "SELECT COALESCE(MAX(sequence_in_bucket), 0) FROM ballot "
                "WHERE election_id = %s AND received_at_bucket = %s",
                (election_id, now_bucket),
            )
            sequence = int(cur.fetchone()[0]) + 1
            revote_serial = self.next_ballot_serial(token_hash)
            cur.execute(
                "INSERT INTO ballot (ballot_id, election_id, blind_token_hash, encrypted_vote, zk_proof, "
                "received_at_bucket, sequence_in_bucket, revote_serial, receipt_hash, accepted_candidate_id) "
                "VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)",
                (
                    ballot_id,
                    election_id,
                    token_hash,
                    json.dumps(encrypted_vote, ensure_ascii=False, sort_keys=True),
                    zk_proof,
                    now_bucket,
                    sequence,
                    revote_serial,
                    receipt_hash,
                    accepted_candidate_id,
                ),
            )
            cur.execute(
                "SELECT ballot_id, election_id, blind_token_hash, encrypted_vote, zk_proof, "
                "received_at_bucket, sequence_in_bucket, revote_serial, receipt_hash, accepted_candidate_id "
                "FROM ballot WHERE ballot_id = %s",
                (ballot_id,),
            )
            ballot = self._row_to_ballot(cur.fetchone())
            self._conn.commit()
        self.append_audit(
            "ballot-box",
            "ballot_accepted",
            {
                "ballot_id": ballot_id,
                "election_id": election_id,
                "receipt_hash": receipt_hash,
                "token_hash": token_hash,
            },
        )
        return ballot

    def public_ballots(self, election_id: str) -> list[Ballot]:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "SELECT ballot_id, election_id, blind_token_hash, encrypted_vote, zk_proof, "
                "received_at_bucket, sequence_in_bucket, revote_serial, receipt_hash, accepted_candidate_id "
                "FROM ballot WHERE election_id = %s "
                "ORDER BY received_at_bucket, sequence_in_bucket",
                (election_id,),
            )
            return [self._row_to_ballot(r) for r in cur.fetchall()]

    def find_ballot_by_receipt(self, election_id: str, receipt_hash: str) -> Ballot | None:
        with self._lock, self._conn.cursor() as cur:
            cur.execute(
                "SELECT ballot_id, election_id, blind_token_hash, encrypted_vote, zk_proof, "
                "received_at_bucket, sequence_in_bucket, revote_serial, receipt_hash, accepted_candidate_id "
                "FROM ballot WHERE election_id = %s AND receipt_hash = %s "
                "ORDER BY revote_serial DESC LIMIT 1",
                (election_id, receipt_hash),
            )
            row = cur.fetchone()
            return self._row_to_ballot(row) if row else None

    def tally(self, election_id: str) -> dict[str, Any]:
        with self._lock, self._conn.cursor() as cur:
            election = self.get_election(election_id)
            cur.execute(
                """
                SELECT b.accepted_candidate_id
                FROM ballot b
                JOIN (
                    SELECT blind_token_hash, MAX(revote_serial) AS max_serial
                    FROM ballot WHERE election_id = %s
                    GROUP BY blind_token_hash
                ) latest ON b.blind_token_hash = latest.blind_token_hash
                       AND b.revote_serial = latest.max_serial
                WHERE b.election_id = %s
                """,
                (election_id, election_id),
            )
            rows = cur.fetchall()
            counts = {c.candidate_id: 0 for c in election.candidates}
            for row in rows:
                counts[str(row[0])] += 1
            result = {"election_id": election_id, "accepted_ballots": len(rows), "counts": counts}
        self.append_audit("tally", "tally_computed", result)
        return result

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    def append_audit(self, component: str, event_type: str, payload: dict[str, Any]) -> AuditLogEntry:
        with self._lock, self._conn.cursor() as cur:
            cur.execute("SELECT log_hash FROM audit_log ORDER BY log_id DESC LIMIT 1")
            row = cur.fetchone()
            prev_hash = str(row[0]) if row else "0" * 64
            occurred_at = utc_now()
            material = canonical_json(
                {
                    "component": component,
                    "event_type": event_type,
                    "occurred_at": occurred_at.isoformat(),
                    "payload": payload,
                    "prev_hash": prev_hash,
                }
            )
            log_hash = sha256_hex(material)
            cur.execute(
                "INSERT INTO audit_log (prev_hash, log_hash, component, event_type, payload, occurred_at) "
                "VALUES (%s, %s, %s, %s, %s::jsonb, %s) RETURNING log_id",
                (
                    prev_hash,
                    log_hash,
                    component,
                    event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    occurred_at,
                ),
            )
            log_id = int(cur.fetchone()[0])
            self._conn.commit()
        return AuditLogEntry(
            log_id=log_id,
            prev_hash=prev_hash,
            log_hash=log_hash,
            component=component,
            event_type=event_type,
            payload=json.loads(json.dumps(payload, ensure_ascii=False)),
            occurred_at=occurred_at,
        )

    def verify_audit_chain(
        self,
        from_log_id: int = 0,
        expected_prev_hash: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            return _verify_chain(
                self.audit_logs,
                from_log_id=from_log_id,
                expected_prev_hash=expected_prev_hash,
            )
