from __future__ import annotations

import argparse
import json
import signal
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .repository import InMemoryRepository
from .service import VotingService
from .sqlite_repository import SqliteRepository


def json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")


class VotingRequestHandler(BaseHTTPRequestHandler):
    # Re-assigned in main() once the storage backend is chosen.
    service: VotingService = VotingService()

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_error(self, status: HTTPStatus, code: str, message: str) -> None:
        """Standardised error envelope. See docs/api/openapi.yaml#ApiError."""
        self._send_json(status, {"error": {"code": code, "message": message}})

    def _send_json(self, status: HTTPStatus, data: Any) -> None:
        payload = json_bytes(data)
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_OPTIONS(self) -> None:
        self._send_json(HTTPStatus.NO_CONTENT, {})

    def _send_text(self, status: HTTPStatus, body: str, content_type: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def _wants_prometheus(self, parsed_url: Any) -> bool:
        """Decide whether the client asked for Prometheus text exposition format.

        Honour either ``?format=prometheus`` for one-off curls or the standard
        ``Accept: text/plain`` / ``Accept: application/openmetrics-text`` that
        Prometheus and OpenMetrics scrapers send.
        """
        query = parse_qs(parsed_url.query or "")
        if "prometheus" in query.get("format", []):
            return True
        accept = (self.headers.get("Accept") or "").lower()
        return "text/plain" in accept or "openmetrics-text" in accept

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        path = parsed_url.path.strip("/").split("/")
        try:
            if path == ["health"]:
                self._send_json(HTTPStatus.OK, {"status": "ok"})
                return
            if path == ["elections"]:
                self._send_json(
                    HTTPStatus.OK,
                    {"elections": [election.to_dict() for election in self.service.repository.list_elections()]},
                )
                return
            if len(path) == 2 and path[0] == "elections":
                self._send_json(HTTPStatus.OK, self.service.repository.get_election(path[1]).to_dict())
                return
            if len(path) == 3 and path[0] == "elections" and path[2] == "bulletin-board":
                self._send_json(HTTPStatus.OK, self.service.public_board(path[1]))
                return
            if len(path) == 3 and path[0] == "elections" and path[2] == "tally":
                self._send_json(HTTPStatus.OK, self.service.tally(path[1]))
                return
            if len(path) == 4 and path[0] == "elections" and path[2] == "receipts":
                self._send_json(HTTPStatus.OK, self.service.verify_receipt(path[1], path[3]))
                return
            if path == ["audit-log"]:
                self._send_json(
                    HTTPStatus.OK,
                    {"audit_log": [entry.to_dict() for entry in self.service.repository.audit_logs]},
                )
                return
            if path == ["audit-log", "verify"]:
                self._send_json(HTTPStatus.OK, self.service.verify_audit_chain())
                return
            if path == ["metrics"]:
                if self._wants_prometheus(parsed_url):
                    self._send_text(
                        HTTPStatus.OK,
                        self.service.metrics_prometheus(),
                        "text/plain; version=0.0.4; charset=utf-8",
                    )
                else:
                    self._send_json(HTTPStatus.OK, self.service.metrics_summary())
                return
            self._send_error(HTTPStatus.NOT_FOUND, "not_found", "resource not found")
        except KeyError as exc:
            self._send_error(HTTPStatus.NOT_FOUND, "not_found", str(exc))
        except ValueError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, "bad_request", str(exc))

    def do_POST(self) -> None:
        path = urlparse(self.path).path.strip("/").split("/")
        try:
            body = self._read_json()
            if path == ["elections"]:
                self._send_json(HTTPStatus.CREATED, self.service.repository.create_election(body).to_dict())
                return
            if len(path) == 3 and path[0] == "elections" and path[2] == "authenticate":
                self._send_json(
                    HTTPStatus.OK,
                    self.service.authenticate_voter(
                        path[1],
                        str(body.get("certificate_serial", "")),
                        str(body.get("birthdate", "")),
                    ),
                )
                return
            if len(path) == 3 and path[0] == "elections" and path[2] == "issue-token":
                self._send_json(HTTPStatus.CREATED, self.service.issue_token(path[1], str(body["voter_hash"])))
                return
            if len(path) == 3 and path[0] == "elections" and path[2] == "prepare-vote":
                self._send_json(HTTPStatus.OK, self.service.prepare_vote(path[1], str(body["candidate_id"])))
                return
            if len(path) == 3 and path[0] == "elections" and path[2] == "ballots":
                self._send_json(
                    HTTPStatus.CREATED,
                    self.service.submit_ballot(
                        path[1],
                        str(body["blind_token"]),
                        body["encrypted_vote"],
                        str(body["zk_proof"]),
                    ),
                )
                return
            self._send_error(HTTPStatus.NOT_FOUND, "not_found", "resource not found")
        except KeyError as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, "missing_field", f"missing or unknown field: {exc}")
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self._send_error(HTTPStatus.BAD_REQUEST, "bad_request", str(exc))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8787, type=int)
    parser.add_argument(
        "--storage",
        default="memory",
        choices=["memory", "sqlite", "postgres"],
        help="Storage backend (memory=volatile, sqlite=durable single-host, postgres=multi-host)",
    )
    parser.add_argument(
        "--sqlite-path",
        default="voting.sqlite3",
        help="SQLite database file path (used when --storage=sqlite)",
    )
    parser.add_argument(
        "--dsn",
        default="",
        help="PostgreSQL DSN, e.g. postgresql://user:pw@host:5432/voting (used when --storage=postgres)",
    )
    args = parser.parse_args()
    if args.storage == "sqlite":
        repository = SqliteRepository(args.sqlite_path)
    elif args.storage == "postgres":
        if not args.dsn:
            parser.error("--dsn is required when --storage=postgres")
        # Imported lazily so installations that never use Postgres do not
        # need the psycopg dependency on disk.
        from .postgres_repository import PostgresRepository
        repository = PostgresRepository(args.dsn)
    else:
        repository = InMemoryRepository()
    VotingRequestHandler.service = VotingService(repository=repository)
    server = ThreadingHTTPServer((args.host, args.port), VotingRequestHandler)
    install_graceful_shutdown(server)
    print(
        f"Internet Voting System API listening on http://{args.host}:{args.port} "
        f"(storage={args.storage})",
        flush=True,
    )
    server.serve_forever()


def install_graceful_shutdown(server: ThreadingHTTPServer) -> None:
    """Register SIGINT / SIGTERM handlers that shut the server down cleanly.

    `serve_forever()` blocks the main thread, so `server.shutdown()` must be
    invoked from another thread. We do so via a one-shot daemon thread.

    On Windows, only SIGINT and SIGBREAK can be installed from Python; SIGTERM
    is silently ignored by the OS. That is acceptable: the docker images run
    on Linux, where SIGTERM is the standard `docker stop` signal, and our
    handler correctly turns it into a clean shutdown there.
    """
    def _shutdown(signum: int, frame: object) -> None:  # type: ignore[unused-argument]
        threading.Thread(target=server.shutdown, name="ivs-shutdown", daemon=True).start()

    for sig_name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        sig = getattr(signal, sig_name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, _shutdown)
        except (ValueError, OSError):
            # Non-main thread or unsupported on this platform; skip silently.
            continue


if __name__ == "__main__":
    main()
