const GENESIS_PREV_HASH = "0".repeat(64);

export class ApiError extends Error {
  constructor(status, code, message) {
    super(`HTTP ${status} ${code}: ${message}`);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.message = message;
  }
}

export class VotingClient {
  constructor(baseUrl, options = {}) {
    const parsed = new URL(baseUrl);
    if (!["http:", "https:"].includes(parsed.protocol)) {
      throw new ValueError("baseUrl must be http:// or https://");
    }
    this.baseUrl = parsed.toString().replace(/\/$/, "");
    this.fetchImpl = options.fetchImpl ?? globalThis.fetch;
    if (typeof this.fetchImpl !== "function") {
      throw new Error("fetch is not available; pass { fetchImpl }");
    }
  }

  async request(method, path, options = {}) {
    const url = new URL(`${this.baseUrl}${path}`);
    for (const [key, value] of Object.entries(options.query ?? {})) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
    const headers = { Accept: options.accept ?? "application/json" };
    const init = { method, headers };
    if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.body);
    }
    const response = await this.fetchImpl(url, init);
    const contentType = response.headers?.get?.("content-type")?.toLowerCase?.() ?? "";
    if (!response.ok) {
      await raiseApiError(response, contentType);
    }
    if ((options.accept ?? "").startsWith("text/")) {
      return response.text();
    }
    return response.status === 204 ? {} : response.json();
  }

  health() {
    return this.request("GET", "/health");
  }

  async listElections() {
    const data = await this.request("GET", "/elections");
    return data.elections;
  }

  getElection(electionId) {
    return this.request("GET", `/elections/${encodeURIComponent(electionId)}`);
  }

  bulletinBoard(electionId) {
    return this.request("GET", `/elections/${encodeURIComponent(electionId)}/bulletin-board`);
  }

  tally(electionId) {
    return this.request("GET", `/elections/${encodeURIComponent(electionId)}/tally`);
  }

  verifyReceipt(electionId, receiptHash) {
    return this.request(
      "GET",
      `/elections/${encodeURIComponent(electionId)}/receipts/${encodeURIComponent(receiptHash)}`,
    );
  }

  metrics(options = {}) {
    if (options.prometheus) {
      return this.request("GET", "/metrics", {
        query: { format: "prometheus" },
        accept: "text/plain",
      });
    }
    return this.request("GET", "/metrics");
  }

  auditLogPage(options = {}) {
    return this.request("GET", "/audit-log", {
      query: { after: options.after ?? 0, limit: options.limit ?? 200 },
    });
  }

  async *iterAuditLog(options = {}) {
    let after = 0;
    const pageSize = options.pageSize ?? 200;
    for (;;) {
      const page = await this.auditLogPage({ after, limit: pageSize });
      for (const entry of page.audit_log) {
        yield entry;
      }
      if (!page.has_more) {
        return;
      }
      after = page.next_after;
    }
  }

  auditCheckpoints(options = {}) {
    return this.request("GET", "/audit-log/checkpoints", {
      query: { interval: options.interval ?? 1000, limit: options.limit ?? 10 },
    });
  }

  verifyAuditChain(options = {}) {
    return this.request("GET", "/audit-log/verify", {
      query: {
        from: options.fromLogId || undefined,
        prev_hash: options.prevHash || undefined,
      },
    });
  }

  verifyAuditChainLocally() {
    return verifyAuditEntriesLocally(this.iterAuditLog());
  }
}

export class ValueError extends Error {
  constructor(message) {
    super(message);
    this.name = "ValueError";
  }
}

export async function verifyAuditEntriesLocally(entries) {
  let previous = GENESIS_PREV_HASH;
  let count = 0;
  for await (const entry of entries) {
    count += 1;
    if (entry.prev_hash !== previous) {
      return {
        valid: false,
        broken_at: entry.log_id,
        broken_reason: "prev_hash_mismatch",
        total: count,
      };
    }
    const material = canonicalJson({
      component: entry.component,
      event_type: entry.event_type,
      occurred_at: String(entry.occurred_at).replace(/Z$/, "+00:00"),
      payload: entry.payload,
      prev_hash: previous,
    });
    if ((await sha256Hex(material)) !== entry.log_hash) {
      return {
        valid: false,
        broken_at: entry.log_id,
        broken_reason: "log_hash_mismatch",
        total: count,
      };
    }
    previous = entry.log_hash;
  }
  return { valid: true, total: count, head_hash: previous };
}

export function canonicalJson(value) {
  return JSON.stringify(sortForJson(value));
}

async function raiseApiError(response, contentType) {
  let code = "unknown";
  let message = await response.text();
  if (contentType.includes("application/json") && message) {
    try {
      const data = JSON.parse(message);
      if (data?.error && typeof data.error === "object") {
        code = String(data.error.code ?? code);
        message = String(data.error.message ?? message);
      }
    } catch {
      // Keep the raw message.
    }
  }
  throw new ApiError(response.status, code, message);
}

function sortForJson(value) {
  if (Array.isArray(value)) {
    return value.map(sortForJson);
  }
  if (value && typeof value === "object") {
    const sorted = {};
    for (const key of Object.keys(value).sort()) {
      sorted[key] = sortForJson(value[key]);
    }
    return sorted;
  }
  return value;
}

async function sha256Hex(text) {
  const bytes = new TextEncoder().encode(text);
  const subtle = globalThis.crypto?.subtle ?? (await import("node:crypto")).webcrypto.subtle;
  const digest = await subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}
