from __future__ import annotations

import argparse
import json
import queue
import random
import statistics
import string
import threading
import time
from dataclasses import dataclass, replace
from http.client import HTTPConnection, HTTPResponse
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class LoadTestConfig:
    base_url: str
    election_id: str
    voters: int
    concurrency: int
    timeout: float
    verify_receipts: bool
    candidate_ids: tuple[str, ...]


@dataclass
class FlowResult:
    ok: bool
    elapsed_ms: float
    status_code: int | None = None
    error: str | None = None


class ApiClient:
    def __init__(self, base_url: str, timeout: float) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme != "http":
            raise ValueError("loadtest.py supports http:// endpoints only")
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
            data = self._read_json(response)
            return response.status, data
        finally:
            conn.close()

    @staticmethod
    def _read_json(response: HTTPResponse) -> dict[str, Any]:
        raw = response.read()
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))


def random_serial(index: int) -> str:
    suffix = "".join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
    return f"LOAD-{index:08d}-{suffix}"


def assert_success(status: int, data: dict[str, Any], label: str) -> None:
    if status < 200 or status >= 300:
        message = data.get("error", {}).get("message") if isinstance(data.get("error"), dict) else data
        raise RuntimeError(f"{label} failed with HTTP {status}: {message}")


def fetch_candidate_ids(config: LoadTestConfig) -> tuple[str, ...]:
    client = ApiClient(config.base_url, config.timeout)
    status, election = client.request("GET", f"/elections/{config.election_id}")
    assert_success(status, election, "get election")
    candidate_ids = tuple(str(candidate["candidate_id"]) for candidate in election.get("candidates", []))
    if not candidate_ids:
        raise RuntimeError(f"election {config.election_id} has no candidates")
    return candidate_ids


def pick_candidate_id(config: LoadTestConfig, index: int) -> str:
    if not config.candidate_ids:
        raise RuntimeError("candidate_ids is empty; fetch election metadata before running the load test")
    return config.candidate_ids[index % len(config.candidate_ids)]


def run_voter_flow(config: LoadTestConfig, index: int) -> FlowResult:
    client = ApiClient(config.base_url, config.timeout)
    started = time.perf_counter()
    try:
        status, auth = client.request(
            "POST",
            f"/elections/{config.election_id}/authenticate",
            {"certificate_serial": random_serial(index), "birthdate": "1980-01-01"},
        )
        assert_success(status, auth, "authenticate")

        status, token = client.request(
            "POST",
            f"/elections/{config.election_id}/issue-token",
            {"voter_hash": auth["voter_hash"]},
        )
        assert_success(status, token, "issue-token")

        candidate_id = pick_candidate_id(config, index)
        status, prepared = client.request(
            "POST",
            f"/elections/{config.election_id}/prepare-vote",
            {"candidate_id": candidate_id},
        )
        assert_success(status, prepared, "prepare-vote")

        status, receipt = client.request(
            "POST",
            f"/elections/{config.election_id}/ballots",
            {
                "blind_token": token["blind_token"],
                "encrypted_vote": prepared["encrypted_vote"],
                "zk_proof": prepared["zk_proof"],
            },
        )
        assert_success(status, receipt, "ballots")

        if config.verify_receipts:
            status, verified = client.request(
                "GET",
                f"/elections/{config.election_id}/receipts/{receipt['receipt_hash']}",
            )
            assert_success(status, verified, "receipt verification")
            if not verified.get("found") or not verified.get("integrity_ok"):
                raise RuntimeError("receipt verification failed integrity check")

        elapsed_ms = (time.perf_counter() - started) * 1000
        return FlowResult(ok=True, elapsed_ms=elapsed_ms, status_code=status)
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return FlowResult(ok=False, elapsed_ms=elapsed_ms, error=str(exc))


def worker(config: LoadTestConfig, jobs: queue.Queue[int], results: list[FlowResult], lock: threading.Lock) -> None:
    while True:
        try:
            index = jobs.get_nowait()
        except queue.Empty:
            return
        try:
            result = run_voter_flow(config, index)
            with lock:
                results.append(result)
        finally:
            jobs.task_done()


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * ratio)))
    return ordered[index]


def run_load_test(config: LoadTestConfig) -> dict[str, Any]:
    if not config.candidate_ids:
        raise ValueError("candidate_ids must not be empty")
    jobs: queue.Queue[int] = queue.Queue()
    for index in range(config.voters):
        jobs.put(index)

    results: list[FlowResult] = []
    lock = threading.Lock()
    started = time.perf_counter()
    threads = [
        threading.Thread(target=worker, args=(config, jobs, results, lock), daemon=True)
        for _ in range(config.concurrency)
    ]
    for thread in threads:
        thread.start()
    jobs.join()
    elapsed_seconds = time.perf_counter() - started

    successful = [result for result in results if result.ok]
    failed = [result for result in results if not result.ok]
    latencies = [result.elapsed_ms for result in successful]
    return {
        "base_url": config.base_url,
        "election_id": config.election_id,
        "voters": config.voters,
        "concurrency": config.concurrency,
        "verify_receipts": config.verify_receipts,
        "candidate_count": len(config.candidate_ids),
        "elapsed_seconds": round(elapsed_seconds, 3),
        "throughput_flows_per_second": round(len(results) / elapsed_seconds, 2) if elapsed_seconds else 0,
        "success": len(successful),
        "failed": len(failed),
        "latency_ms": {
            "min": round(min(latencies), 2) if latencies else 0,
            "median": round(statistics.median(latencies), 2) if latencies else 0,
            "p95": round(percentile(latencies, 0.95), 2),
            "max": round(max(latencies), 2) if latencies else 0,
        },
        "sample_errors": [result.error for result in failed[:5]],
    }


def parse_args() -> LoadTestConfig:
    parser = argparse.ArgumentParser(description="Run full-flow load tests against the prototype voting API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8787")
    parser.add_argument("--election-id", default="demo-2026")
    parser.add_argument("--voters", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--verify-receipts", action="store_true")
    args = parser.parse_args()
    if args.voters < 1:
        raise ValueError("--voters must be greater than 0")
    if args.concurrency < 1:
        raise ValueError("--concurrency must be greater than 0")
    return LoadTestConfig(
        base_url=args.base_url,
        election_id=args.election_id,
        voters=args.voters,
        concurrency=min(args.concurrency, args.voters),
        timeout=args.timeout,
        verify_receipts=args.verify_receipts,
        candidate_ids=(),
    )


def main() -> None:
    config = parse_args()
    config = replace(config, candidate_ids=fetch_candidate_ids(config))
    report = run_load_test(config)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
