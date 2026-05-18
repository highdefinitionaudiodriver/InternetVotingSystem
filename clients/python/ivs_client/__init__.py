"""ivs_client — a stdlib-only Python SDK for the InternetVotingSystem API.

Designed for third-party auditors, election observers, and integration tests.
Imports nothing outside the Python standard library so it runs on any host
that can already run the prototype API itself.

Public surface::

    from ivs_client import VotingClient, ApiError

    client = VotingClient("http://127.0.0.1:8787")
    client.health()
    client.list_elections()
    client.verify_receipt("demo-2026", receipt_hash)
    client.verify_audit_chain_locally("demo-2026")  # full recompute

See ``clients/python/README.md`` for the rationale and threat model.
"""

from .client import ApiError, VotingClient

__all__ = ["ApiError", "VotingClient"]
__version__ = "0.1.0"
