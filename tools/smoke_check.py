from __future__ import annotations

import argparse
import json
import random
import string
from dataclasses import dataclass
from http.client import HTTPConnection, HTTPResponse
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class SmokeConfig:
    base_url: str
    election_id: str
    timeout: float


class ApiClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "http":
            raise ValueError("smoke_check.py supports http:// endpoints only")
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 80
        self.prefix = parsed.path.rstrip("/")
        self.timeout = timeout

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
        conn = HTTPConnection(self.host, self.port, timeout=self.timeout)
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        try:
            conn.request(method, f"{self.prefix}{path}", body=payload, headers=headers)
            response = conn.getresponse()
            return response.status, self._read_json(response)
        finally:
            conn.close()

    @staticmethod
    def _read_json(response: HTTPResponse) -> dict[str, Any]:
        raw = response.read()
        return json.loads(raw.decode("utf-8")) if raw else {}


def assert_success(status: int, data: dict[str, Any], label: str) -> None:
    if status < 200 or status >= 300:
        message = data.get("error", {}).get("message") if isinstance(data.get("error"), dict) else data
        raise RuntimeError(f"{label} failed with HTTP {status}: {message}")


def random_serial() -> str:
    suffix = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(12))
    return f"SMOKE-{suffix}"


def run_smoke_check(config: SmokeConfig) -> dict[str, Any]:
    client = ApiClient(config.base_url, config.timeout)

    status, health = client.request("GET", "/health")
    assert_success(status, health, "health")
    if health.get("status") != "ok":
        raise RuntimeError(f"health returned unexpected payload: {health}")

    status, election = client.request("GET", f"/elections/{config.election_id}")
    assert_success(status, election, "get election")
    candidates = election.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"election {config.election_id} has no candidates")
    candidate_id = str(candidates[0]["candidate_id"])

    status, auth = client.request(
        "POST",
        f"/elections/{config.election_id}/authenticate",
        {"certificate_serial": random_serial(), "birthdate": "1980-01-01"},
    )
    assert_success(status, auth, "authenticate")

    status, token = client.request(
        "POST",
        f"/elections/{config.election_id}/issue-token",
        {"voter_hash": auth["voter_hash"]},
    )
    assert_success(status, token, "issue-token")

    status, prepared = client.request(
        "POST",
        f"/elections/{config.election_id}/prepare-vote",
        {"candidate_id": candidate_id},
    )
    assert_success(status, prepared, "prepare-vote")

    status, ballot = client.request(
        "POST",
        f"/elections/{config.election_id}/ballots",
        {
            "blind_token": token["blind_token"],
            "encrypted_vote": prepared["encrypted_vote"],
            "zk_proof": prepared["zk_proof"],
        },
    )
    assert_success(status, ballot, "ballots")

    status, receipt = client.request(
        "GET",
        f"/elections/{config.election_id}/receipts/{ballot['receipt_hash']}",
    )
    assert_success(status, receipt, "receipt verification")
    if not receipt.get("found") or not receipt.get("integrity_ok"):
        raise RuntimeError(f"receipt verification failed: {receipt}")

    status, audit = client.request("GET", "/audit-log/verify")
    assert_success(status, audit, "audit verification")
    if not audit.get("valid"):
        raise RuntimeError(f"audit chain verification failed: {audit}")

    return {
        "status": "ok",
        "election_id": config.election_id,
        "candidate_id": candidate_id,
        "ballot_id": ballot["ballot_id"],
        "receipt_hash": ballot["receipt_hash"],
        "audit_head_hash": audit["head_hash"],
    }


def parse_args() -> SmokeConfig:
    parser = argparse.ArgumentParser(description="Run a single end-to-end smoke check against a running API server.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8787")
    parser.add_argument("--election-id", default="demo-2026")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args()
    return SmokeConfig(base_url=args.base_url, election_id=args.election_id, timeout=args.timeout)


def main() -> None:
    report = run_smoke_check(parse_args())
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
