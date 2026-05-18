import assert from "node:assert/strict";
import { test } from "node:test";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { ApiError, ValueError, VotingClient, canonicalJson, verifyAuditEntriesLocally } from "../src/index.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(HERE, "../src/index.js");
const GENESIS = "0".repeat(64);

test("routes health, election listing, and prometheus metrics", async () => {
  const calls = [];
  const client = new VotingClient("http://example.test/api", {
    fetchImpl: async (url, init) => {
      calls.push({ url: String(url), init });
      if (String(url).endsWith("/health")) {
        return jsonResponse({ status: "ok" });
      }
      if (String(url).endsWith("/elections")) {
        return jsonResponse({ elections: [{ election_id: "demo-2026" }] });
      }
      return textResponse("internet_voting_total_elections 1\n");
    },
  });

  assert.equal((await client.health()).status, "ok");
  assert.equal((await client.listElections())[0].election_id, "demo-2026");
  assert.match(await client.metrics({ prometheus: true }), /internet_voting_total_elections/);
  assert.equal(calls[2].url, "http://example.test/api/metrics?format=prometheus");
  assert.equal(calls[2].init.headers.Accept, "text/plain");
});

test("api error envelope is exposed as ApiError", async () => {
  const client = new VotingClient("http://example.test", {
    fetchImpl: async () => jsonResponse({ error: { code: "bad_request", message: "not hex" } }, 400),
  });

  await assert.rejects(
    () => client.verifyReceipt("demo-2026", "not-hex"),
    (error) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.status, 400);
      assert.equal(error.code, "bad_request");
      return true;
    },
  );
});

test("audit log iterator follows pagination", async () => {
  const pages = [
    { audit_log: [{ log_id: 1 }], has_more: true, next_after: 1 },
    { audit_log: [{ log_id: 2 }], has_more: false, next_after: 2 },
  ];
  const urls = [];
  const client = new VotingClient("http://example.test", {
    fetchImpl: async (url) => {
      urls.push(String(url));
      return jsonResponse(pages.shift());
    },
  });

  const ids = [];
  for await (const entry of client.iterAuditLog({ pageSize: 1 })) {
    ids.push(entry.log_id);
  }

  assert.deepEqual(ids, [1, 2]);
  assert.deepEqual(urls, [
    "http://example.test/audit-log?after=0&limit=1",
    "http://example.test/audit-log?after=1&limit=1",
  ]);
});

test("local audit replay verifies canonical hashes", async () => {
  const first = await makeEntry({
    log_id: 1,
    component: "auth",
    event_type: "voter_authenticated",
    occurred_at: "2026-05-18T00:00:00Z",
    payload: { nested: { b: 2, a: 1 } },
    prev_hash: GENESIS,
  });
  const second = await makeEntry({
    log_id: 2,
    component: "ballot",
    event_type: "ballot_recorded",
    occurred_at: "2026-05-18T00:00:01Z",
    payload: { ballot_id: "b-1" },
    prev_hash: first.log_hash,
  });

  assert.deepEqual(await verifyAuditEntriesLocally([first, second]), {
    valid: true,
    total: 2,
    head_hash: second.log_hash,
  });

  const broken = { ...second, prev_hash: GENESIS };
  const result = await verifyAuditEntriesLocally([first, broken]);
  assert.equal(result.valid, false);
  assert.equal(result.broken_reason, "prev_hash_mismatch");
});

test("base URL and public method signatures avoid individual-number fields", () => {
  assert.throws(() => new VotingClient("ftp://example.test"), ValueError);
  const source = readFileSync(SRC, "utf-8");
  const forbidden = ["mynumber", "individual_number", "個人番号", "my_number"];
  for (const name of Object.getOwnPropertyNames(VotingClient.prototype)) {
    if (name === "constructor" || name.startsWith("_")) {
      continue;
    }
    const method = VotingClient.prototype[name];
    const signature = String(method).split("{", 1)[0].toLowerCase();
    for (const token of forbidden) {
      assert.doesNotMatch(signature, new RegExp(token.toLowerCase()));
    }
  }
  assert.doesNotMatch(source, /individual_number|my_number|mynumber/);
});

async function makeEntry(entry) {
  const log_hash = await sha256Hex(canonicalJson({
    component: entry.component,
    event_type: entry.event_type,
    occurred_at: entry.occurred_at.replace(/Z$/, "+00:00"),
    payload: entry.payload,
    prev_hash: entry.prev_hash,
  }));
  return { ...entry, log_hash };
}

async function sha256Hex(text) {
  const bytes = new TextEncoder().encode(text);
  const digest = await globalThis.crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function jsonResponse(body, status = 200) {
  return response(JSON.stringify(body), status, "application/json; charset=utf-8");
}

function textResponse(body, status = 200) {
  return response(body, status, "text/plain; charset=utf-8");
}

function response(body, status, contentType) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: (name) => (name.toLowerCase() === "content-type" ? contentType : null) },
    json: async () => JSON.parse(body),
    text: async () => body,
  };
}
