from __future__ import annotations

import uuid
from typing import Any

from .crypto import DemoCryptoSuite
from .repository import InMemoryRepository


class VotingService:
    def __init__(self, repository: InMemoryRepository | None = None, crypto: DemoCryptoSuite | None = None) -> None:
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
