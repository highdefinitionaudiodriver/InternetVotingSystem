from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from .service import VotingService


def json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True).encode("utf-8")


class VotingRequestHandler(BaseHTTPRequestHandler):
    service = VotingService()

    def log_message(self, format: str, *args: Any) -> None:
        return

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

    def do_GET(self) -> None:
        path = urlparse(self.path).path.strip("/").split("/")
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
            if path == ["audit-log"]:
                self._send_json(
                    HTTPStatus.OK,
                    {"audit_log": [entry.to_dict() for entry in self.service.repository.audit_logs]},
                )
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except KeyError as exc:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": str(exc)})
        except ValueError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

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
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})
        except KeyError as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": f"missing or unknown field: {exc}"})
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8787, type=int)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), VotingRequestHandler)
    print(f"Internet Voting System API listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
