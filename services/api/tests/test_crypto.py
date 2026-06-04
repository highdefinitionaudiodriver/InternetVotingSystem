"""Focused unit tests for the DemoCryptoSuite and crypto helpers.

The crypto module is the most security-sensitive part of the system, yet it
was previously only exercised indirectly through the service layer. These
tests assert the invariants directly: token signing/verification, ballot
encryption round-trips, ZK-proof acceptance/rejection, and the encoding
helpers. (The suite is a labelled demo adapter; these tests guard the
prototype's boundaries, not production-grade cryptographic security.)
"""
from __future__ import annotations

import unittest

from internet_voting_system.crypto import (
    DemoCryptoSuite,
    b64url,
    canonical_json,
    sha256_hex,
    unb64url,
)


class EncodingHelpersTest(unittest.TestCase):
    def test_b64url_roundtrip_for_various_lengths(self) -> None:
        for n in range(0, 40):
            data = bytes(range(n))
            self.assertEqual(unb64url(b64url(data)), data)

    def test_b64url_is_padding_free(self) -> None:
        self.assertNotIn("=", b64url(b"\x00\x01\x02"))

    def test_sha256_hex_accepts_str_and_bytes_consistently(self) -> None:
        self.assertEqual(sha256_hex("abc"), sha256_hex(b"abc"))

    def test_canonical_json_is_key_order_independent(self) -> None:
        a = canonical_json({"b": 1, "a": 2})
        b = canonical_json({"a": 2, "b": 1})
        self.assertEqual(a, b)
        # And it is compact (no spaces).
        self.assertNotIn(b" ", a)


class TokenTest(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = DemoCryptoSuite.with_ephemeral_keys()
        self.election = "demo-2026"
        self.voter_hash = self.suite.voter_hash("CERT-1", self.election, "salt")

    def test_issue_then_verify_roundtrip(self) -> None:
        token = self.suite.issue_token(self.election, self.voter_hash, serial=1)
        payload = self.suite.verify_token(token, self.election)
        self.assertEqual(payload["election_id"], self.election)
        self.assertEqual(payload["serial"], 1)

    def test_verify_rejects_wrong_election(self) -> None:
        token = self.suite.issue_token(self.election, self.voter_hash, serial=1)
        with self.assertRaises(ValueError):
            self.suite.verify_token(token, "other-election")

    def test_verify_rejects_tampered_signature(self) -> None:
        token = self.suite.issue_token(self.election, self.voter_hash, serial=1)
        # Flip a character in the encoded envelope.
        tampered = token[:-2] + ("A" if token[-1] != "A" else "B")
        with self.assertRaises(ValueError):
            self.suite.verify_token(tampered, self.election)

    def test_verify_rejects_token_from_different_key(self) -> None:
        other = DemoCryptoSuite.with_ephemeral_keys()
        token = other.issue_token(self.election, self.voter_hash, serial=1)
        with self.assertRaises(ValueError):
            self.suite.verify_token(token, self.election)

    def test_verify_rejects_malformed_token(self) -> None:
        with self.assertRaises(ValueError):
            self.suite.verify_token("not-a-valid-token", self.election)

    def test_issue_token_uses_fresh_nonce(self) -> None:
        t1 = self.suite.issue_token(self.election, self.voter_hash, serial=1)
        t2 = self.suite.issue_token(self.election, self.voter_hash, serial=1)
        self.assertNotEqual(t1, t2)


class BallotEncryptionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = DemoCryptoSuite.with_ephemeral_keys()
        self.election = "demo-2026"

    def test_encrypt_decrypt_roundtrip(self) -> None:
        enc = self.suite.encrypt_vote(self.election, "cand-a")
        self.assertEqual(self.suite.decrypt_vote(self.election, enc), "cand-a")

    def test_ciphertext_differs_from_plaintext(self) -> None:
        enc = self.suite.encrypt_vote(self.election, "cand-a")
        self.assertNotIn("cand-a", unb64url(enc["ciphertext"]).decode("utf-8", "replace"))

    def test_decrypt_rejects_election_mismatch(self) -> None:
        enc = self.suite.encrypt_vote(self.election, "cand-a")
        with self.assertRaises(ValueError):
            self.suite.decrypt_vote("other-election", enc)


class ZkProofTest(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = DemoCryptoSuite.with_ephemeral_keys()
        self.election = "demo-2026"
        self.candidates = {"cand-a", "cand-b"}

    def test_valid_proof_returns_candidate(self) -> None:
        enc = self.suite.encrypt_vote(self.election, "cand-a")
        proof = self.suite.make_zk_proof(self.election, "cand-a", enc)
        result = self.suite.verify_zk_proof(self.election, self.candidates, enc, proof)
        self.assertEqual(result, "cand-a")

    def test_proof_rejected_when_candidate_not_in_set(self) -> None:
        enc = self.suite.encrypt_vote(self.election, "cand-z")
        proof = self.suite.make_zk_proof(self.election, "cand-z", enc)
        with self.assertRaises(ValueError):
            self.suite.verify_zk_proof(self.election, self.candidates, enc, proof)

    def test_tampered_proof_is_rejected(self) -> None:
        enc = self.suite.encrypt_vote(self.election, "cand-a")
        proof = self.suite.make_zk_proof(self.election, "cand-a", enc)
        tampered = proof[:-1] + ("A" if proof[-1] != "A" else "B")
        with self.assertRaises(ValueError):
            self.suite.verify_zk_proof(self.election, self.candidates, enc, tampered)


class VoterHashTest(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = DemoCryptoSuite.with_ephemeral_keys()

    def test_deterministic(self) -> None:
        a = self.suite.voter_hash("CERT-1", "e1", "salt")
        b = self.suite.voter_hash("CERT-1", "e1", "salt")
        self.assertEqual(a, b)

    def test_salt_changes_hash(self) -> None:
        a = self.suite.voter_hash("CERT-1", "e1", "salt-a")
        b = self.suite.voter_hash("CERT-1", "e1", "salt-b")
        self.assertNotEqual(a, b)

    def test_election_changes_hash(self) -> None:
        a = self.suite.voter_hash("CERT-1", "e1", "salt")
        b = self.suite.voter_hash("CERT-1", "e2", "salt")
        self.assertNotEqual(a, b)


if __name__ == "__main__":
    unittest.main()
