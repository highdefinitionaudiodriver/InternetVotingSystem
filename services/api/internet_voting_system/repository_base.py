"""Repository protocol shared by in-memory and SQLite implementations.

The voting service depends only on this protocol, so the storage backend can
be swapped between volatile in-memory state (useful for tests and demos) and
durable persistent state (SQLite for single-host pilots, PostgreSQL later)
without touching service-layer code.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from .crypto import canonical_json, sha256_hex
from .models import AuditLogEntry, Ballot, Election, VoterStatus


GENESIS_PREV_HASH = "0" * 64


def _verify_chain(
    entries: list[AuditLogEntry],
    *,
    from_log_id: int = 0,
    expected_prev_hash: str | None = None,
) -> dict[str, Any]:
    """Shared hash-chain replay used by every Repository implementation.

    Behaviour matches the docstring on ``InMemoryRepository.verify_audit_chain``.
    Extracted so that the three storage backends produce byte-identical
    outputs and so checkpoint semantics live in one place.
    """
    if from_log_id < 0:
        return {"valid": False, "broken_at": from_log_id, "total": len(entries)}
    if from_log_id == 0:
        prev = GENESIS_PREV_HASH
    else:
        if expected_prev_hash is None:
            return {
                "valid": False,
                "broken_at": from_log_id,
                "total": len(entries),
                "reason": "expected_prev_hash is required when from_log_id > 0",
            }
        prev = expected_prev_hash

    tail = [e for e in entries if e.log_id > from_log_id]
    for entry in tail:
        material = canonical_json(
            {
                "component": entry.component,
                "event_type": entry.event_type,
                "occurred_at": entry.occurred_at.isoformat(),
                "payload": entry.payload,
                "prev_hash": prev,
            }
        )
        if entry.prev_hash != prev or entry.log_hash != sha256_hex(material):
            return {"valid": False, "broken_at": entry.log_id, "total": len(entries)}
        prev = entry.log_hash
    return {
        "valid": True,
        "total": len(entries),
        "verified_from": from_log_id,
        "head_hash": prev,
    }


def bucket_5_minutes(dt: datetime) -> datetime:
    """Round a timestamp down to the nearest 5-minute bucket.

    This deliberately coarsens the recorded receipt time so that the bulletin
    board cannot be used to correlate a voter's submission timing with the
    server-side log of identity authentication.
    """
    return dt.replace(minute=dt.minute - (dt.minute % 5), second=0, microsecond=0)


@runtime_checkable
class Repository(Protocol):
    """Storage operations required by VotingService.

    All methods must be safe to call concurrently. Implementations are
    expected to perform their own locking or rely on the underlying
    database's transactional guarantees.
    """

    audit_logs: list[AuditLogEntry]

    def seed_demo_data(self) -> None: ...
    def list_elections(self) -> list[Election]: ...
    def get_election(self, election_id: str) -> Election: ...
    def create_election(self, data: dict[str, Any]) -> Election: ...
    def set_election_status(self, election_id: str, status: str) -> Election: ...
    def get_or_create_voter_status(self, election_id: str, voter_hash: str) -> VoterStatus: ...
    def mark_token_issued(self, election_id: str, voter_hash: str, token_hash: str) -> VoterStatus: ...
    def next_ballot_serial(self, token_hash: str) -> int: ...
    def store_ballot(
        self,
        ballot_id: str,
        election_id: str,
        token_hash: str,
        encrypted_vote: dict[str, str],
        zk_proof: str,
        receipt_hash: str,
        accepted_candidate_id: str,
    ) -> Ballot: ...
    def public_ballots(self, election_id: str) -> list[Ballot]: ...
    def find_ballot_by_receipt(self, election_id: str, receipt_hash: str) -> Ballot | None: ...
    def tally(self, election_id: str) -> dict[str, Any]: ...
    def append_audit(self, component: str, event_type: str, payload: dict[str, Any]) -> AuditLogEntry: ...
    def verify_audit_chain(
        self,
        from_log_id: int = 0,
        expected_prev_hash: str | None = None,
    ) -> dict[str, Any]: ...
