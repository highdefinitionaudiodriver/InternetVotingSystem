"""SQLite-backed Repository implementation.

This adapter persists elections, voter status, ballots, and the hash-chained
audit log to a single SQLite database file. It satisfies the same Repository
protocol as the in-memory implementation so VotingService can be swapped to
SQLite with no service-layer changes.

Production deployments should replace this with a PostgreSQL-backed
implementation that adds row-level access control and TDE; the schema here is
deliberately compatible.

Notes for Codex:
- All writes occur under ``BEGIN IMMEDIATE`` to obtain a reservable lock,
  which models the ``SELECT ... FOR UPDATE`` semantics required by the design
  document for the token-issuance critical section.
- ``encrypted_vote`` is stored as JSON text (sqlite has no native JSONB).
- ``audit_logs`` is exposed as a property that materialises rows on demand;
  for very large logs this should be replaced with a streaming iterator.
"""

from __future__ import annotations

import json
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from .crypto import canonical_json, sha256_hex
from .models import AuditLogEntry, Ballot, Candidate, Election, VoterStatus, utc_now
from .repository_base import _verify_chain, bucket_5_minutes

_SCHEMA = """
CREATE TABLE IF NOT EXISTS elections (
    election_id   TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    starts_at     TEXT NOT NULL,
    ends_at       TEXT NOT NULL,
    voter_salt    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'open'
);

CREATE TABLE IF NOT EXISTS candidates (
    election_id   TEXT NOT NULL REFERENCES elections(election_id),
    candidate_id  TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    party         TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (election_id, candidate_id)
);

CREATE TABLE IF NOT EXISTS voter_status (
    voter_hash             TEXT NOT NULL,
    election_id            TEXT NOT NULL REFERENCES elections(election_id),
    token_issued           INTEGER NOT NULL DEFAULT 0,
    token_issued_at        TEXT,
    revote_count           INTEGER NOT NULL DEFAULT 0,
    last_issued_token_hash TEXT,
    PRIMARY KEY (election_id, voter_hash)
);

CREATE TABLE IF NOT EXISTS ballots (
    ballot_id            TEXT PRIMARY KEY,
    election_id          TEXT NOT NULL REFERENCES elections(election_id),
    blind_token_hash     TEXT NOT NULL,
    encrypted_vote       TEXT NOT NULL,
    zk_proof             TEXT NOT NULL,
    received_at_bucket   TEXT NOT NULL,
    sequence_in_bucket   INTEGER NOT NULL,
    revote_serial        INTEGER NOT NULL,
    receipt_hash         TEXT NOT NULL,
    accepted_candidate_id TEXT NOT NULL,
    UNIQUE (blind_token_hash, revote_serial)
);
CREATE INDEX IF NOT EXISTS idx_ballots_election ON ballots(election_id);
CREATE INDEX IF NOT EXISTS idx_ballots_receipt ON ballots(election_id, receipt_hash);

CREATE TABLE IF NOT EXISTS audit_log (
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    prev_hash   TEXT NOT NULL,
    log_hash    TEXT NOT NULL,
    component   TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    payload     TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);
"""


def _to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


class SqliteRepository:
    """Durable Repository backed by SQLite.

    Pass ``":memory:"`` to obtain a non-persistent backend that still
    exercises the SQL code paths (used by tests).
    """

    def __init__(self, database_path: str = "voting.sqlite3", seed: bool = True) -> None:
        self._lock = threading.RLock()
        # ``check_same_thread=False`` is safe because every connection access is
        # guarded by ``self._lock``; this lets the threading HTTP server reuse
        # one connection without per-request handover.
        self._conn = sqlite3.connect(database_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(_SCHEMA)
        if seed and not self._conn.execute("SELECT 1 FROM elections LIMIT 1").fetchone():
            self.seed_demo_data()

    # ------------------------------------------------------------------
    # audit_logs is exposed as a property so the protocol can keep a
    # list-like accessor identical to the in-memory implementation.
    # ------------------------------------------------------------------
    @property
    def audit_logs(self) -> list[AuditLogEntry]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT log_id, prev_hash, log_hash, component, event_type, payload, occurred_at "
                "FROM audit_log ORDER BY log_id"
            ).fetchall()
        return [self._row_to_audit(row) for row in rows]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _row_to_audit(self, row: sqlite3.Row) -> AuditLogEntry:
        return AuditLogEntry(
            log_id=int(row["log_id"]),
            prev_hash=str(row["prev_hash"]),
            log_hash=str(row["log_hash"]),
            component=str(row["component"]),
            event_type=str(row["event_type"]),
            payload=json.loads(row["payload"]),
            occurred_at=_from_iso(str(row["occurred_at"])),
        )

    def _row_to_election(self, row: sqlite3.Row) -> Election:
        candidates = [
            Candidate(str(c["candidate_id"]), str(c["display_name"]), str(c["party"]))
            for c in self._conn.execute(
                "SELECT candidate_id, display_name, party FROM candidates WHERE election_id = ? ORDER BY candidate_id",
                (row["election_id"],),
            ).fetchall()
        ]
        return Election(
            election_id=str(row["election_id"]),
            title=str(row["title"]),
            starts_at=_from_iso(str(row["starts_at"])),
            ends_at=_from_iso(str(row["ends_at"])),
            voter_salt=str(row["voter_salt"]),
            candidates=candidates,
            status=str(row["status"]),
        )

    def _row_to_ballot(self, row: sqlite3.Row) -> Ballot:
        return Ballot(
            ballot_id=str(row["ballot_id"]),
            election_id=str(row["election_id"]),
            blind_token_hash=str(row["blind_token_hash"]),
            encrypted_vote=json.loads(row["encrypted_vote"]),
            zk_proof=str(row["zk_proof"]),
            received_at_bucket=_from_iso(str(row["received_at_bucket"])),
            sequence_in_bucket=int(row["sequence_in_bucket"]),
            revote_serial=int(row["revote_serial"]),
            receipt_hash=str(row["receipt_hash"]),
            accepted_candidate_id=str(row["accepted_candidate_id"]),
        )

    # ------------------------------------------------------------------
    # Seed
    # ------------------------------------------------------------------
    def seed_demo_data(self) -> None:
        now = utc_now()
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute(
                "INSERT OR IGNORE INTO elections (election_id, title, starts_at, ends_at, voter_salt, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    "demo-2026",
                    "デモ選挙 2026",
                    _to_iso(now - timedelta(days=1)),
                    _to_iso(now + timedelta(days=7)),
                    secrets.token_hex(16),
                    "open",
                ),
            )
            for cid, name, party in [
                ("cand-a", "候補者A", "未来党"),
                ("cand-b", "候補者B", "市民ネット"),
                ("cand-c", "候補者C", "無所属"),
            ]:
                self._conn.execute(
                    "INSERT OR IGNORE INTO candidates (election_id, candidate_id, display_name, party) "
                    "VALUES (?, ?, ?, ?)",
                    ("demo-2026", cid, name, party),
                )
            self._conn.execute("COMMIT")
            self.append_audit("system", "election_seeded", {"election_id": "demo-2026"})

    # ------------------------------------------------------------------
    # Elections
    # ------------------------------------------------------------------
    def list_elections(self) -> list[Election]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM elections ORDER BY election_id").fetchall()
            return [self._row_to_election(row) for row in rows]

    def get_election(self, election_id: str) -> Election:
        with self._lock:
            row = self._conn.execute("SELECT * FROM elections WHERE election_id = ?", (election_id,)).fetchone()
            if row is None:
                raise KeyError("election not found")
            return self._row_to_election(row)

    def create_election(self, data: dict[str, Any]) -> Election:
        candidates = [
            Candidate(str(item["candidate_id"]), str(item["display_name"]), str(item.get("party", "")))
            for item in data["candidates"]
        ]
        if len({c.candidate_id for c in candidates}) != len(candidates):
            raise ValueError("candidate_id must be unique")
        starts_at = _from_iso(str(data["starts_at"]))
        ends_at = _from_iso(str(data["ends_at"]))
        if starts_at >= ends_at:
            raise ValueError("starts_at must be earlier than ends_at")
        election_id = str(data["election_id"])
        status = str(data.get("status", "open"))
        with self._lock:
            existing = self._conn.execute("SELECT 1 FROM elections WHERE election_id = ?", (election_id,)).fetchone()
            if existing:
                raise ValueError("election already exists")
            self._conn.execute("BEGIN IMMEDIATE")
            self._conn.execute(
                "INSERT INTO elections (election_id, title, starts_at, ends_at, voter_salt, status) VALUES (?, ?, ?, ?, ?, ?)",
                (election_id, str(data["title"]), _to_iso(starts_at), _to_iso(ends_at), secrets.token_hex(16), status),
            )
            for c in candidates:
                self._conn.execute(
                    "INSERT INTO candidates (election_id, candidate_id, display_name, party) VALUES (?, ?, ?, ?)",
                    (election_id, c.candidate_id, c.display_name, c.party),
                )
            self._conn.execute("COMMIT")
            self.append_audit("admin", "election_created", {"election_id": election_id})
            return self.get_election(election_id)

    def set_election_status(self, election_id: str, status: str) -> Election:
        if status not in ("open", "closed"):
            raise ValueError("status must be 'open' or 'closed'")
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            cur = self._conn.execute(
                "UPDATE elections SET status = ? WHERE election_id = ?",
                (status, election_id),
            )
            if cur.rowcount == 0:
                self._conn.execute("ROLLBACK")
                raise KeyError("election not found")
            self._conn.execute("COMMIT")
            return self.get_election(election_id)

    # ------------------------------------------------------------------
    # Voter status
    # ------------------------------------------------------------------
    def get_or_create_voter_status(self, election_id: str, voter_hash: str) -> VoterStatus:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM voter_status WHERE election_id = ? AND voter_hash = ?",
                (election_id, voter_hash),
            ).fetchone()
            if row is None:
                self._conn.execute(
                    "INSERT INTO voter_status (voter_hash, election_id) VALUES (?, ?)",
                    (voter_hash, election_id),
                )
                row = self._conn.execute(
                    "SELECT * FROM voter_status WHERE election_id = ? AND voter_hash = ?",
                    (election_id, voter_hash),
                ).fetchone()
            return VoterStatus(
                voter_hash=str(row["voter_hash"]),
                election_id=str(row["election_id"]),
                token_issued=bool(row["token_issued"]),
                token_issued_at=_from_iso(str(row["token_issued_at"])) if row["token_issued_at"] else None,
                revote_count=int(row["revote_count"]),
                last_issued_token_hash=row["last_issued_token_hash"],
            )

    def mark_token_issued(self, election_id: str, voter_hash: str, token_hash: str) -> VoterStatus:
        with self._lock:
            # BEGIN IMMEDIATE models SELECT ... FOR UPDATE: it reserves the
            # write lock so concurrent issuers serialise on the voter row.
            self._conn.execute("BEGIN IMMEDIATE")
            self.get_or_create_voter_status(election_id, voter_hash)
            now_iso = _to_iso(utc_now())
            self._conn.execute(
                "UPDATE voter_status SET token_issued = 1, token_issued_at = ?, "
                "revote_count = revote_count + 1, last_issued_token_hash = ? "
                "WHERE election_id = ? AND voter_hash = ?",
                (now_iso, token_hash, election_id, voter_hash),
            )
            self._conn.execute("COMMIT")
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
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM ballots WHERE blind_token_hash = ?",
                (token_hash,),
            ).fetchone()
            return int(row["n"]) + 1

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
        with self._lock:
            now_bucket = bucket_5_minutes(utc_now())
            self._conn.execute("BEGIN IMMEDIATE")
            seq_row = self._conn.execute(
                "SELECT COALESCE(MAX(sequence_in_bucket), 0) AS m FROM ballots "
                "WHERE election_id = ? AND received_at_bucket = ?",
                (election_id, _to_iso(now_bucket)),
            ).fetchone()
            sequence = int(seq_row["m"]) + 1
            revote_serial = self.next_ballot_serial(token_hash)
            self._conn.execute(
                "INSERT INTO ballots (ballot_id, election_id, blind_token_hash, encrypted_vote, zk_proof, "
                "received_at_bucket, sequence_in_bucket, revote_serial, receipt_hash, accepted_candidate_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    ballot_id,
                    election_id,
                    token_hash,
                    json.dumps(encrypted_vote, ensure_ascii=False, sort_keys=True),
                    zk_proof,
                    _to_iso(now_bucket),
                    sequence,
                    revote_serial,
                    receipt_hash,
                    accepted_candidate_id,
                ),
            )
            self._conn.execute("COMMIT")
            row = self._conn.execute("SELECT * FROM ballots WHERE ballot_id = ?", (ballot_id,)).fetchone()
            ballot = self._row_to_ballot(row)
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
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM ballots WHERE election_id = ? ORDER BY received_at_bucket, sequence_in_bucket",
                (election_id,),
            ).fetchall()
            return [self._row_to_ballot(row) for row in rows]

    def find_ballot_by_receipt(self, election_id: str, receipt_hash: str) -> Ballot | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM ballots WHERE election_id = ? AND receipt_hash = ? "
                "ORDER BY revote_serial DESC LIMIT 1",
                (election_id, receipt_hash),
            ).fetchone()
            return self._row_to_ballot(row) if row else None

    def tally(self, election_id: str) -> dict[str, Any]:
        with self._lock:
            election = self.get_election(election_id)
            # For each token, take the ballot with the largest revote_serial.
            rows = self._conn.execute(
                """
                SELECT b.accepted_candidate_id AS cid
                FROM ballots b
                JOIN (
                    SELECT blind_token_hash, MAX(revote_serial) AS max_serial
                    FROM ballots WHERE election_id = ?
                    GROUP BY blind_token_hash
                ) latest ON b.blind_token_hash = latest.blind_token_hash
                       AND b.revote_serial = latest.max_serial
                WHERE b.election_id = ?
                """,
                (election_id, election_id),
            ).fetchall()
            counts = {c.candidate_id: 0 for c in election.candidates}
            for row in rows:
                counts[str(row["cid"])] += 1
            result = {"election_id": election_id, "accepted_ballots": len(rows), "counts": counts}
            self.append_audit("tally", "tally_computed", result)
            return result

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    def append_audit(self, component: str, event_type: str, payload: dict[str, Any]) -> AuditLogEntry:
        with self._lock:
            last = self._conn.execute(
                "SELECT log_hash FROM audit_log ORDER BY log_id DESC LIMIT 1"
            ).fetchone()
            prev_hash = str(last["log_hash"]) if last else "0" * 64
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
            cur = self._conn.execute(
                "INSERT INTO audit_log (prev_hash, log_hash, component, event_type, payload, occurred_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    prev_hash,
                    log_hash,
                    component,
                    event_type,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    _to_iso(occurred_at),
                ),
            )
            return AuditLogEntry(
                log_id=int(cur.lastrowid),
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
