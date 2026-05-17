from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class Candidate:
    candidate_id: str
    display_name: str
    party: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"candidate_id": self.candidate_id, "display_name": self.display_name, "party": self.party}


@dataclass
class Election:
    election_id: str
    title: str
    starts_at: datetime
    ends_at: datetime
    voter_salt: str
    candidates: list[Candidate]
    status: str = "open"

    def candidate_ids(self) -> set[str]:
        return {candidate.candidate_id for candidate in self.candidates}

    def is_open(self, now: datetime | None = None) -> bool:
        current = now or utc_now()
        return self.status == "open" and self.starts_at <= current <= self.ends_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "election_id": self.election_id,
            "title": self.title,
            "starts_at": iso(self.starts_at),
            "ends_at": iso(self.ends_at),
            "status": self.status,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


@dataclass
class VoterStatus:
    voter_hash: str
    election_id: str
    token_issued: bool = False
    token_issued_at: datetime | None = None
    revote_count: int = 0
    last_issued_token_hash: str | None = None


@dataclass
class Ballot:
    ballot_id: str
    election_id: str
    blind_token_hash: str
    encrypted_vote: dict[str, str]
    zk_proof: str
    received_at_bucket: datetime
    sequence_in_bucket: int
    revote_serial: int
    receipt_hash: str
    accepted_candidate_id: str = field(repr=False)

    def public_record(self) -> dict[str, Any]:
        return {
            "ballot_id": self.ballot_id,
            "election_id": self.election_id,
            "blind_token_hash": self.blind_token_hash,
            "received_at_bucket": iso(self.received_at_bucket),
            "sequence_in_bucket": self.sequence_in_bucket,
            "revote_serial": self.revote_serial,
            "receipt_hash": self.receipt_hash,
        }


@dataclass
class AuditLogEntry:
    log_id: int
    prev_hash: str
    log_hash: str
    component: str
    event_type: str
    payload: dict[str, Any]
    occurred_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "log_id": self.log_id,
            "prev_hash": self.prev_hash,
            "log_hash": self.log_hash,
            "component": self.component,
            "event_type": self.event_type,
            "payload": self.payload,
            "occurred_at": iso(self.occurred_at),
        }
