from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from typing import Any


def canonical_json(data: dict[str, Any]) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(data: bytes | str) -> str:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def unb64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


@dataclass(frozen=True)
class DemoCryptoSuite:
    """Deterministic demo crypto adapter.

    This class preserves production boundaries while avoiding hand-rolled
    production cryptography in the prototype. Replace it with audited
    RFC 9474/ElGamal/ZKP implementations before any real-world use.
    """

    token_signing_key: bytes
    ballot_encryption_key: bytes

    @classmethod
    def with_ephemeral_keys(cls) -> "DemoCryptoSuite":
        return cls(secrets.token_bytes(32), secrets.token_bytes(32))

    def voter_hash(self, certificate_serial: str, election_id: str, salt: str) -> str:
        return sha256_hex(f"{certificate_serial}|{election_id}|{salt}")

    def issue_token(self, election_id: str, voter_hash: str, serial: int) -> str:
        payload = {
            "election_id": election_id,
            "nonce": b64url(secrets.token_bytes(24)),
            "serial": serial,
            "voter_commitment": sha256_hex(voter_hash.encode("utf-8")),
        }
        signature = hmac.new(self.token_signing_key, canonical_json(payload), hashlib.sha384).digest()
        return b64url(canonical_json({"payload": payload, "signature": b64url(signature)}))

    def verify_token(self, token: str, election_id: str) -> dict[str, Any]:
        try:
            envelope = json.loads(unb64url(token))
            payload = envelope["payload"]
            signature = unb64url(envelope["signature"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("invalid token format") from exc

        expected = hmac.new(self.token_signing_key, canonical_json(payload), hashlib.sha384).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid token signature")
        if payload.get("election_id") != election_id:
            raise ValueError("token election mismatch")
        return payload

    def encrypt_vote(self, election_id: str, candidate_id: str) -> dict[str, str]:
        nonce = secrets.token_bytes(16)
        plaintext = canonical_json({"election_id": election_id, "candidate_id": candidate_id})
        stream = hmac.new(self.ballot_encryption_key, nonce + election_id.encode("utf-8"), hashlib.sha256).digest()
        ciphertext = bytes(a ^ stream[i % len(stream)] for i, a in enumerate(plaintext))
        return {"nonce": b64url(nonce), "ciphertext": b64url(ciphertext)}

    def decrypt_vote(self, election_id: str, encrypted_vote: dict[str, str]) -> str:
        nonce = unb64url(encrypted_vote["nonce"])
        ciphertext = unb64url(encrypted_vote["ciphertext"])
        stream = hmac.new(self.ballot_encryption_key, nonce + election_id.encode("utf-8"), hashlib.sha256).digest()
        plaintext = bytes(a ^ stream[i % len(stream)] for i, a in enumerate(ciphertext))
        data = json.loads(plaintext)
        if data.get("election_id") != election_id:
            raise ValueError("encrypted vote election mismatch")
        return str(data["candidate_id"])

    def token_hash(self, token: str) -> str:
        return sha256_hex(token)

    def receipt_hash(self, ballot_id: str, token_hash: str) -> str:
        return sha256_hex(f"{ballot_id}|{token_hash}")

    def make_zk_proof(self, election_id: str, candidate_id: str, encrypted_vote: dict[str, str]) -> str:
        proof_payload = canonical_json(
            {
                "candidate_id": candidate_id,
                "election_id": election_id,
                "encrypted_vote": encrypted_vote,
                "purpose": "demo-membership-proof",
            }
        )
        return b64url(hmac.new(self.ballot_encryption_key, proof_payload, hashlib.sha256).digest())

    def verify_zk_proof(
        self,
        election_id: str,
        candidate_ids: set[str],
        encrypted_vote: dict[str, str],
        zk_proof: str,
    ) -> str:
        candidate_id = self.decrypt_vote(election_id, encrypted_vote)
        if candidate_id not in candidate_ids:
            raise ValueError("candidate is not in election candidate set")
        expected = self.make_zk_proof(election_id, candidate_id, encrypted_vote)
        if not hmac.compare_digest(zk_proof, expected):
            raise ValueError("invalid zero-knowledge proof")
        return candidate_id
