"""HTTP client + local audit-chain replay for the InternetVotingSystem API.

The client makes a deliberate set of design choices:

- **Stdlib only.** Anyone running CPython 3.11+ can use this SDK without
  pulling in requests / httpx / pydantic. Auditors install zero packages.
- **No hidden state.** Every method maps 1:1 to a documented API route.
- **Replay verification is local.** ``verify_audit_chain_locally`` walks
  the chain via paginated reads, recomputes each ``log_hash`` from
  ``canonical_json + SHA-256``, and only trusts an entry when the local
  recomputation matches the server-reported value. Operators that hand a
  chain to an auditor can be checked end-to-end on the auditor's laptop.
- **No mynumber.** The SDK exposes no parameter named ``mynumber``,
  ``individual_number``, ``個人番号``, etc. The corresponding regression
  test asserts the public surface stays clean.
"""

from __future__ import annotations

import hashlib
import json
from http.client import HTTPConnection, HTTPResponse, HTTPSConnection
from typing import Any, Iterable, Iterator
from urllib.parse import urlencode, urlparse


GENESIS_PREV_HASH = "0" * 64


class ApiError(RuntimeError):
    """Raised when the API returns a non-2xx status code.

    The structured ``{error: {code, message}}`` envelope produced by the
    API is preserved on the instance so callers can dispatch on
    ``error.code`` without re-parsing the response body.
    """

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(f"HTTP {status} {code}: {message}")
        self.status = status
        self.code = code
        self.message = message


def _canonical_json(data: dict[str, Any]) -> bytes:
    """Match the canonicalisation used by services/api crypto.canonical_json."""
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class VotingClient:
    """Synchronous HTTP client backed by ``http.client``.

    Parameters
    ----------
    base_url:
        Root of the API, e.g. ``http://127.0.0.1:8787`` or
        ``https://voting.example.com``.
    timeout:
        Per-request timeout in seconds.
    """

    def __init__(self, base_url: str, *, timeout: float = 10.0) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("base_url must be http:// or https://")
        self._scheme = parsed.scheme
        self._host = parsed.hostname or "127.0.0.1"
        self._port = parsed.port or (443 if parsed.scheme == "https" else 80)
        self._prefix = parsed.path.rstrip("/")
        self._timeout = float(timeout)

    # ------------------------------------------------------------------
    # Low-level transport
    # ------------------------------------------------------------------
    def _connection(self) -> HTTPConnection:
        if self._scheme == "https":
            return HTTPSConnection(self._host, self._port, timeout=self._timeout)
        return HTTPConnection(self._host, self._port, timeout=self._timeout)

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        accept: str = "application/json",
    ) -> Any:
        url = f"{self._prefix}{path}"
        if query:
            url = f"{url}?{urlencode({k: v for k, v in query.items() if v is not None})}"
        payload = (
            json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        )
        headers = {"Accept": accept}
        if body is not None:
            headers["Content-Type"] = "application/json"
        conn = self._connection()
        try:
            conn.request(method, url, body=payload, headers=headers)
            response: HTTPResponse = conn.getresponse()
            raw = response.read()
            content_type = (response.getheader("Content-Type") or "").lower()
            if response.status >= 400:
                self._raise_api_error(response.status, raw, content_type)
            if accept.startswith("text/"):
                return raw.decode("utf-8")
            return json.loads(raw.decode("utf-8")) if raw else {}
        finally:
            conn.close()

    @staticmethod
    def _raise_api_error(status: int, raw: bytes, content_type: str) -> None:
        code = "unknown"
        message = raw.decode("utf-8", errors="replace") if raw else ""
        if "application/json" in content_type and raw:
            try:
                data = json.loads(raw.decode("utf-8"))
                err = data.get("error") if isinstance(data, dict) else None
                if isinstance(err, dict):
                    code = str(err.get("code") or code)
                    message = str(err.get("message") or message)
            except json.JSONDecodeError:
                pass
        raise ApiError(status, code, message)

    # ------------------------------------------------------------------
    # Public API methods (1:1 with openapi.yaml)
    # ------------------------------------------------------------------
    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def list_elections(self) -> list[dict[str, Any]]:
        return self._request("GET", "/elections")["elections"]

    def get_election(self, election_id: str) -> dict[str, Any]:
        return self._request("GET", f"/elections/{election_id}")

    def bulletin_board(self, election_id: str) -> dict[str, Any]:
        return self._request("GET", f"/elections/{election_id}/bulletin-board")

    def tally(self, election_id: str) -> dict[str, Any]:
        return self._request("GET", f"/elections/{election_id}/tally")

    def verify_receipt(self, election_id: str, receipt_hash: str) -> dict[str, Any]:
        return self._request(
            "GET", f"/elections/{election_id}/receipts/{receipt_hash}"
        )

    def metrics(self, *, prometheus: bool = False) -> Any:
        if prometheus:
            return self._request("GET", "/metrics", query={"format": "prometheus"}, accept="text/plain")
        return self._request("GET", "/metrics")

    def audit_log_page(self, *, after: int = 0, limit: int = 200) -> dict[str, Any]:
        return self._request("GET", "/audit-log", query={"after": after, "limit": limit})

    def iter_audit_log(self, *, page_size: int = 200) -> Iterator[dict[str, Any]]:
        """Stream every audit entry by paginating in the background."""
        after = 0
        while True:
            page = self.audit_log_page(after=after, limit=page_size)
            for entry in page["audit_log"]:
                yield entry
            if not page["has_more"]:
                return
            after = page["next_after"]

    def audit_checkpoints(self, *, interval: int = 1000, limit: int = 10) -> dict[str, Any]:
        return self._request(
            "GET",
            "/audit-log/checkpoints",
            query={"interval": interval, "limit": limit},
        )

    def verify_audit_chain(
        self,
        *,
        from_log_id: int = 0,
        prev_hash: str | None = None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {}
        if from_log_id:
            query["from"] = from_log_id
        if prev_hash:
            query["prev_hash"] = prev_hash
        return self._request("GET", "/audit-log/verify", query=query or None)

    # ------------------------------------------------------------------
    # Local replay: trust nothing the server says.
    # ------------------------------------------------------------------
    def verify_audit_chain_locally(self) -> dict[str, Any]:
        """Replay the full chain on the auditor's machine.

        Useful when the auditor explicitly wants to avoid trusting the
        server's own /audit-log/verify endpoint. Returns a dict with::

            {
              "valid": bool,
              "total": int,
              "head_hash": str,            # only when valid
              "broken_at": int,            # only when invalid
              "broken_reason": "prev_hash_mismatch" | "log_hash_mismatch",
            }
        """
        return _verify_entries_locally(self.iter_audit_log())


def _verify_entries_locally(entries: Iterable[dict[str, Any]]) -> dict[str, Any]:
    prev = GENESIS_PREV_HASH
    count = 0
    for entry in entries:
        count += 1
        if entry["prev_hash"] != prev:
            return {
                "valid": False,
                "broken_at": entry["log_id"],
                "broken_reason": "prev_hash_mismatch",
                "total": count,
            }
        material = _canonical_json(
            {
                "component": entry["component"],
                "event_type": entry["event_type"],
                # The server emits ISO with a trailing 'Z' but stores datetimes
                # without offset; canonical_json uses isoformat() of the raw
                # datetime, which after `astimezone(UTC)` produces "+00:00".
                # Audit entries from the API already carry that string verbatim
                # in occurred_at when the server emits it via iso(), so we
                # normalise here.
                "occurred_at": entry["occurred_at"].replace("Z", "+00:00"),
                "payload": entry["payload"],
                "prev_hash": prev,
            }
        )
        if _sha256_hex(material) != entry["log_hash"]:
            return {
                "valid": False,
                "broken_at": entry["log_id"],
                "broken_reason": "log_hash_mismatch",
                "total": count,
            }
        prev = entry["log_hash"]
    return {"valid": True, "total": count, "head_hash": prev}
