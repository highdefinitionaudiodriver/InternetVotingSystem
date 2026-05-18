# InternetVotingSystem TypeScript SDK

Dependency-free fetch-based SDK for browser, Node 18+, and auditors who want
to replay audit logs locally.

This package is source-distributed from the repository. Publishing to npm is
out of scope for the prototype; pin a repository commit instead.

## Quick Start

```ts
import { VotingClient } from "./src/index.js";

const client = new VotingClient("http://127.0.0.1:8787");
console.log(await client.health());

const checkpoints = await client.auditCheckpoints({ interval: 1000 });
const latest = checkpoints.checkpoints[0];
console.log(await client.verifyAuditChain({
  fromLogId: latest.log_id,
  prevHash: latest.log_hash,
}));

const local = await client.verifyAuditChainLocally();
if (!local.valid) {
  throw new Error(`audit chain broke at ${local.broken_at}`);
}
```

## Privacy Invariants

- The SDK exposes no public method parameter for an individual number
  (マイナンバー).
- The SDK never writes request or response payloads to disk.
- `verifyAuditChainLocally()` recomputes each audit log hash client-side
  instead of trusting the API's own `/audit-log/verify` response.

## Test

```bash
cd clients/typescript
node --test tests/*.test.mjs
```
