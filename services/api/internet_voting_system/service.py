from __future__ import annotations

import re
import uuid
from typing import Any

from .crypto import DemoCryptoSuite
from .repository import InMemoryRepository
from .repository_base import Repository

RECEIPT_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _escape_prometheus_label(value: str) -> str:
    """Escape a label value per the Prometheus text exposition spec.

    Backslash, double-quote, and newline are the only characters that must be
    escaped (https://prometheus.io/docs/instrumenting/exposition_formats/).
    """
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class VotingService:
    def __init__(self, repository: Repository | None = None, crypto: DemoCryptoSuite | None = None) -> None:
        self.repository = repository or InMemoryRepository()
        self.crypto = crypto or DemoCryptoSuite.with_ephemeral_keys()

    def authenticate_voter(self, election_id: str, certificate_serial: str, birthdate: str) -> dict[str, Any]:
        election = self.repository.get_election(election_id)
        if not election.is_open():
            raise ValueError("election is not open")
        if not certificate_serial or len(certificate_serial) < 6:
            raise ValueError("certificate_serial is invalid")
        if not birthdate:
            raise ValueError("birthdate is required for voter registry matching")
        voter_hash = self.crypto.voter_hash(certificate_serial, election_id, election.voter_salt)
        status = self.repository.get_or_create_voter_status(election_id, voter_hash)
        self.repository.append_audit(
            "jpki-gateway",
            "voter_authenticated",
            {"election_id": election_id, "voter_hash": voter_hash, "token_issued": status.token_issued},
        )
        return {
            "election_id": election_id,
            "voter_hash": voter_hash,
            "eligible": True,
            "token_issued": status.token_issued,
            "revote_count": status.revote_count,
        }

    def issue_token(self, election_id: str, voter_hash: str) -> dict[str, Any]:
        election = self.repository.get_election(election_id)
        if not election.is_open():
            raise ValueError("election is not open")
        status = self.repository.get_or_create_voter_status(election_id, voter_hash)
        serial = status.revote_count + 1
        token = self.crypto.issue_token(election_id, voter_hash, serial)
        token_hash = self.crypto.token_hash(token)
        self.repository.mark_token_issued(election_id, voter_hash, token_hash)
        return {"election_id": election_id, "blind_token": token, "blind_token_hash": token_hash, "revote_count": serial}

    def prepare_vote(self, election_id: str, candidate_id: str) -> dict[str, Any]:
        election = self.repository.get_election(election_id)
        if candidate_id not in election.candidate_ids():
            raise ValueError("candidate not found")
        encrypted_vote = self.crypto.encrypt_vote(election_id, candidate_id)
        zk_proof = self.crypto.make_zk_proof(election_id, candidate_id, encrypted_vote)
        return {"encrypted_vote": encrypted_vote, "zk_proof": zk_proof}

    def submit_ballot(
        self,
        election_id: str,
        blind_token: str,
        encrypted_vote: dict[str, str],
        zk_proof: str,
    ) -> dict[str, Any]:
        election = self.repository.get_election(election_id)
        if not election.is_open():
            raise ValueError("election is not open")
        self.crypto.verify_token(blind_token, election_id)
        candidate_id = self.crypto.verify_zk_proof(election_id, election.candidate_ids(), encrypted_vote, zk_proof)
        token_hash = self.crypto.token_hash(blind_token)
        ballot_id = str(uuid.uuid4())
        receipt_hash = self.crypto.receipt_hash(ballot_id, token_hash)
        ballot = self.repository.store_ballot(
            ballot_id=ballot_id,
            election_id=election_id,
            token_hash=token_hash,
            encrypted_vote=encrypted_vote,
            zk_proof=zk_proof,
            receipt_hash=receipt_hash,
            accepted_candidate_id=candidate_id,
        )
        return ballot.public_record()

    def close_election(self, election_id: str) -> dict[str, Any]:
        """Transition an election from ``open`` to ``closed``.

        Subsequent ``authenticate_voter``, ``issue_token``, and
        ``submit_ballot`` calls will be rejected because :class:`Election`
        only marks itself ``is_open`` while ``status == "open"`` and the
        current time is within ``[starts_at, ends_at]``. This mirrors
        Article 55 of the Public Office Election Act (closing the ballot
        box at the end of the polling period).
        """
        election = self.repository.set_election_status(election_id, "closed")
        self.repository.append_audit("admin", "election_closed", {"election_id": election_id})
        return election.to_dict()

    def public_board(self, election_id: str) -> dict[str, Any]:
        self.repository.get_election(election_id)
        return {
            "election_id": election_id,
            "ballots": [ballot.public_record() for ballot in self.repository.public_ballots(election_id)],
        }

    def tally(self, election_id: str) -> dict[str, Any]:
        return self.repository.tally(election_id)

    def verify_receipt(self, election_id: str, receipt_hash: str) -> dict[str, Any]:
        """Cast-as-Intended / Recorded-as-Cast verification by receipt hash.

        Returns the public ballot record if found, plus a recomputed receipt
        hash so the client can detect any silent mutation server-side. The
        voter's identity is never returned — only the public record fields.
        """
        if not RECEIPT_HASH_PATTERN.fullmatch(receipt_hash):
            raise ValueError("receipt_hash must be a 64-character lowercase hex string")
        self.repository.get_election(election_id)
        ballot = self.repository.find_ballot_by_receipt(election_id, receipt_hash)
        if ballot is None:
            return {"found": False, "receipt_hash": receipt_hash}
        recomputed = self.crypto.receipt_hash(ballot.ballot_id, ballot.blind_token_hash)
        return {
            "found": True,
            "receipt_hash": receipt_hash,
            "recomputed_receipt_hash": recomputed,
            "integrity_ok": recomputed == receipt_hash,
            "ballot": ballot.public_record(),
        }

    def verify_audit_chain(self) -> dict[str, Any]:
        """Expose audit-log integrity verification (hash-chain replay)."""
        return self.repository.verify_audit_chain()

    def metrics_prometheus(self) -> str:
        """Same data as ``metrics_summary`` rendered in Prometheus text exposition format.

        Output is compatible with the ``text/plain; version=0.0.4`` content type
        consumed by Prometheus and most compatible scrapers (VictoriaMetrics,
        Grafana Agent, etc.). Only the safe-to-expose aggregates are emitted;
        the same privacy posture as ``metrics_summary`` applies.
        """
        summary = self.metrics_summary()
        lines: list[str] = [
            "# HELP internet_voting_total_elections Number of elections registered in this API.",
            "# TYPE internet_voting_total_elections gauge",
            f"internet_voting_total_elections {summary['total_elections']}",
            "# HELP internet_voting_total_ballots_recorded Total ballots stored across all elections.",
            "# TYPE internet_voting_total_ballots_recorded counter",
            f"internet_voting_total_ballots_recorded {summary['total_ballots_recorded']}",
            "# HELP internet_voting_audit_log_entries Number of hash-chained audit log entries.",
            "# TYPE internet_voting_audit_log_entries counter",
            f"internet_voting_audit_log_entries {summary['audit_log_entries']}",
            "# HELP internet_voting_election_ballots Ballots recorded per election.",
            "# TYPE internet_voting_election_ballots gauge",
        ]
        for election in summary["elections"]:
            election_id = _escape_prometheus_label(str(election["election_id"]))
            status = _escape_prometheus_label(str(election["status"]))
            lines.append(
                f'internet_voting_election_ballots{{election_id="{election_id}",status="{status}"}} '
                f"{election['ballots_recorded']}"
            )
        # Prometheus expositions end with a trailing newline.
        return "\n".join(lines) + "\n"

    def metrics_summary(self) -> dict[str, Any]:
        """Aggregate operational metrics that are safe to expose publicly.

        The response intentionally contains only counts and per-election ballot
        totals. It never includes voter_hash values, certificate serials,
        ballot identifiers, candidate-level breakdowns, or audit-log payloads,
        so it is safe to scrape from monitoring without leaking information
        that could be cross-referenced with the bulletin board.
        """
        elections = self.repository.list_elections()
        per_election = []
        total_ballots = 0
        for election in elections:
            ballots = self.repository.public_ballots(election.election_id)
            total_ballots += len(ballots)
            per_election.append(
                {
                    "election_id": election.election_id,
                    "status": election.status,
                    "ballots_recorded": len(ballots),
                }
            )
        return {
            "elections": per_election,
            "total_elections": len(elections),
            "total_ballots_recorded": total_ballots,
            "audit_log_entries": len(self.repository.audit_logs),
        }
