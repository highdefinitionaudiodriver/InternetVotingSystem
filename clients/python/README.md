# ivs_client — Python SDK

A stdlib-only Python SDK for the InternetVotingSystem API. Designed for
third-party auditors, election observers, and integration tests.

## Why a separate SDK

- The API surface is stable (OpenAPI 3.1) and the audit-log replay is the
  most security-sensitive consumer pattern. Providing a vetted SDK lowers
  the chance of an auditor introducing a bug in their own re-implementation
  of the hash chain.
- Zero third-party dependencies — `pip install` only the SDK package and
  it works on any host that can run CPython 3.11+.

## Install (editable, from this repo)

```bash
cd clients/python
pip install -e .
```

A real PyPI release is **out of scope** for the prototype; auditors should
pin a commit hash from this repository.

## Quick start

```python
from ivs_client import VotingClient

client = VotingClient("http://127.0.0.1:8787")
print(client.health())
for e in client.list_elections():
    print(e["election_id"], e["status"])

# Fetch a checkpoint and verify only the tail of the chain.
ckpts = client.audit_checkpoints(interval=1000)
latest = ckpts["checkpoints"][0]
print(client.verify_audit_chain(from_log_id=latest["log_id"], prev_hash=latest["log_hash"]))

# Or replay the entire chain locally without trusting the server's verifier.
result = client.verify_audit_chain_locally()
assert result["valid"]
```

## Privacy invariants

- The SDK never accepts or transmits an individual number (マイナンバー).
  The test suite asserts no public method exposes `mynumber` /
  `individual_number` / `個人番号` / `my_number` parameters.
- The SDK never persists request bodies or response payloads to disk. If
  the auditor wants to retain audit-log evidence, they call `iter_audit_log`
  themselves and decide where to write.

## Test it

```bash
cd clients/python
python -m unittest discover -s tests
```
