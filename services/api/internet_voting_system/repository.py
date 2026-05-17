from __future__ import annotations

import json
import secrets
import threading
from datetime import datetime, timedelta, timezone
from typing import Any

from .crypto import canonical_json, sha256_hex
from .models import AuditLogEntry, Ballot, Candidate, Election, VoterStatus, utc_now


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def bucket_5_minutes(dt: datetime) -> datetime:
    return dt.replace(minute=dt.minute - (dt.minute % 5), second=0, microsecond=0)


class InMemoryRepository:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.elections: dict[str, Election] = {}
        self.voters: dict[tuple[str, str], VoterStatus] = {}
        self.ballots: dict[str, Ballot] = {}
        self.ballots_by_token: dict[str, list[str]] = {}
        self.audit_logs: list[AuditLogEntry] = []
        self._bucket_sequences: dict[tuple[str, datetime], int] = {}
        self.seed_demo_data()

    def seed_demo_data(self) -> None:
        now = utc_now()
        election = Election(
            election_id="demo-2026",
            title="デモ選挙 2026",
            starts_at=now - timedelta(days=1),
            ends_at=now + timedelta(days=7),
            voter_salt=secrets.token_hex(16),
            candidates=[
                Candidate("cand-a", "候補者A", "未来党"),
                Candidate("cand-b", "候補者B", "市民ネット"),
                Candidate("cand-c", "候補者C", "無所属"),
            ],
        )
        self.elections[election.election_id] = election
        self.append_audit("system", "election_seeded", {"election_id": election.election_id})

    def list_elections(self) -> list[Election]:
        with self._lock:
            return list(self.elections.values())

    def get_election(self, election_id: str) -> Election:
        with self._lock:
            try:
                return self.elections[election_id]
            except KeyError as exc:
                raise KeyError("election not found") from exc

    def create_election(self, data: dict[str, Any]) -> Election:
        candidates = [
            Candidate(str(item["candidate_id"]), str(item["display_name"]), str(item.get("party", "")))
            for item in data["candidates"]
        ]
        if len({candidate.candidate_id for candidate in candidates}) != len(candidates):
            raise ValueError("candidate_id must be unique")
        election = Election(
            election_id=str(data["election_id"]),
            title=str(data["title"]),
            starts_at=parse_datetime(str(data["starts_at"])),
            ends_at=parse_datetime(str(data["ends_at"])),
            voter_salt=secrets.token_hex(16),
            candidates=candidates,
            status=str(data.get("status", "open")),
        )
        if election.starts_at >= election.ends_at:
            raise ValueError("starts_at must be earlier than ends_at")
        with self._lock:
            if election.election_id in self.elections:
                raise ValueError("election already exists")
            self.elections[election.election_id] = election
            self.append_audit("admin", "election_created", {"election_id": election.election_id})
        return election

    def get_or_create_voter_status(self, election_id: str, voter_hash: str) -> VoterStatus:
        key = (election_id, voter_hash)
        with self._lock:
            if key not in self.voters:
                self.voters[key] = VoterStatus(voter_hash=voter_hash, election_id=election_id)
            return self.voters[key]

    def mark_token_issued(self, election_id: str, voter_hash: str, token_hash: str) -> VoterStatus:
        with self._lock:
            status = self.get_or_create_voter_status(election_id, voter_hash)
            status.token_issued = True
            status.token_issued_at = utc_now()
            status.revote_count += 1
            status.last_issued_token_hash = token_hash
            self.append_audit(
                "blind-signer",
                "token_issued",
                {"election_id": election_id, "token_hash": token_hash, "revote_count": status.revote_count},
            )
            return status

    def next_ballot_serial(self, token_hash: str) -> int:
        with self._lock:
            return len(self.ballots_by_token.get(token_hash, [])) + 1

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
            seq_key = (election_id, now_bucket)
            self._bucket_sequences[seq_key] = self._bucket_sequences.get(seq_key, 0) + 1
            ballot = Ballot(
                ballot_id=ballot_id,
                election_id=election_id,
                blind_token_hash=token_hash,
                encrypted_vote=encrypted_vote,
                zk_proof=zk_proof,
                received_at_bucket=now_bucket,
                sequence_in_bucket=self._bucket_sequences[seq_key],
                revote_serial=self.next_ballot_serial(token_hash),
                receipt_hash=receipt_hash,
                accepted_candidate_id=accepted_candidate_id,
            )
            self.ballots[ballot_id] = ballot
            self.ballots_by_token.setdefault(token_hash, []).append(ballot_id)
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
            return [ballot for ballot in self.ballots.values() if ballot.election_id == election_id]

    def tally(self, election_id: str) -> dict[str, Any]:
        with self._lock:
            election = self.get_election(election_id)
            latest_by_token: dict[str, Ballot] = {}
            for ballot in self.public_ballots(election_id):
                current = latest_by_token.get(ballot.blind_token_hash)
                if current is None or ballot.revote_serial > current.revote_serial:
                    latest_by_token[ballot.blind_token_hash] = ballot

            counts = {candidate.candidate_id: 0 for candidate in election.candidates}
            for ballot in latest_by_token.values():
                counts[ballot.accepted_candidate_id] += 1

            result = {
                "election_id": election_id,
                "accepted_ballots": len(latest_by_token),
                "counts": counts,
            }
            self.append_audit("tally", "tally_computed", result)
            return result

    def append_audit(self, component: str, event_type: str, payload: dict[str, Any]) -> AuditLogEntry:
        prev_hash = self.audit_logs[-1].log_hash if self.audit_logs else "0" * 64
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
        entry = AuditLogEntry(
            log_id=len(self.audit_logs) + 1,
            prev_hash=prev_hash,
            log_hash=sha256_hex(material),
            component=component,
            event_type=event_type,
            payload=json.loads(json.dumps(payload, ensure_ascii=False)),
            occurred_at=occurred_at,
        )
        self.audit_logs.append(entry)
        return entry
