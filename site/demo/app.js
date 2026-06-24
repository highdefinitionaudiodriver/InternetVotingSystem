/*
 * ブラウザ内デモ（バックエンド不要）。
 *
 * services/api の VotingService / DemoCryptoSuite / InMemoryRepository を
 * ブラウザ内に最小移植したもの。append/verify を同一ロジックで実装しているため
 * ハッシュチェーンは内部整合する（Python 実装とのバイト一致は意図しない）。
 *
 * ⚠️ 暗号はデモ用の簡略実装。実際の投票には使用できないこと、サーバーへ
 *    一切送信しないことは index.html のバナーで明示している。
 */

const electionId = "demo-2026";

/* ============================================================
 * 暗号ヘルパー（crypto.py の JS 版・内部整合のみを目的とする）
 * ========================================================== */
const enc = new TextEncoder();
const dec = new TextDecoder();

function bytesToB64url(bytes) {
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function b64urlToBytes(value) {
  const norm = value.replace(/-/g, "+").replace(/_/g, "/");
  const pad = norm.length % 4 ? "=".repeat(4 - (norm.length % 4)) : "";
  const bin = atob(norm + pad);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
  return out;
}

// Python: json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=False)
function canonicalString(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map(canonicalString).join(",") + "]";
  const keys = Object.keys(value).sort();
  return "{" + keys.map((k) => JSON.stringify(k) + ":" + canonicalString(value[k])).join(",") + "}";
}

function canonicalBytes(value) {
  return enc.encode(canonicalString(value));
}

async function sha256Bytes(bytes) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return new Uint8Array(digest);
}

async function sha256Hex(input) {
  const bytes = typeof input === "string" ? enc.encode(input) : input;
  const hash = await sha256Bytes(bytes);
  return [...hash].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function concatBytes(...chunks) {
  const total = chunks.reduce((sum, c) => sum + c.length, 0);
  const out = new Uint8Array(total);
  let offset = 0;
  for (const c of chunks) {
    out.set(c, offset);
    offset += c.length;
  }
  return out;
}

// デモ用の鍵（ページ読み込みごとにエフェメラル）
const tokenSigningKey = crypto.getRandomValues(new Uint8Array(32));
const ballotEncryptionKey = crypto.getRandomValues(new Uint8Array(32));

async function keystream(nonce, eid) {
  return sha256Bytes(concatBytes(nonce, enc.encode(eid), ballotEncryptionKey));
}

async function encryptVote(eid, candidateId) {
  const nonce = crypto.getRandomValues(new Uint8Array(16));
  const plain = canonicalBytes({ election_id: eid, candidate_id: candidateId });
  const ks = await keystream(nonce, eid);
  const cipher = plain.map((b, i) => b ^ ks[i % ks.length]);
  return { nonce: bytesToB64url(nonce), ciphertext: bytesToB64url(cipher) };
}

async function decryptVote(eid, encryptedVote) {
  const nonce = b64urlToBytes(encryptedVote.nonce);
  const cipher = b64urlToBytes(encryptedVote.ciphertext);
  const ks = await keystream(nonce, eid);
  const plain = cipher.map((b, i) => b ^ ks[i % ks.length]);
  const data = JSON.parse(dec.decode(plain));
  if (data.election_id !== eid) throw new Error("encrypted vote election mismatch");
  return String(data.candidate_id);
}

async function voterHashOf(certificateSerial, eid, salt) {
  return sha256Hex(`${certificateSerial}|${eid}|${salt}`);
}

async function issueTokenValue(eid, voterHash, serial) {
  const payload = {
    election_id: eid,
    nonce: bytesToB64url(crypto.getRandomValues(new Uint8Array(24))),
    serial,
    voter_commitment: await sha256Hex(voterHash),
  };
  const signature = await sha256Hex(concatBytes(canonicalBytes(payload), tokenSigningKey));
  return bytesToB64url(canonicalBytes({ payload, signature }));
}

async function verifyTokenValue(token, eid) {
  let envelope;
  try {
    envelope = JSON.parse(dec.decode(b64urlToBytes(token)));
  } catch (err) {
    throw new Error("invalid token format");
  }
  const expected = await sha256Hex(concatBytes(canonicalBytes(envelope.payload), tokenSigningKey));
  if (envelope.signature !== expected) throw new Error("invalid token signature");
  if (envelope.payload.election_id !== eid) throw new Error("token election mismatch");
  return envelope.payload;
}

async function makeZkProof(eid, candidateId, encryptedVote) {
  return sha256Hex(
    concatBytes(
      canonicalBytes({
        candidate_id: candidateId,
        election_id: eid,
        encrypted_vote: encryptedVote,
        purpose: "demo-membership-proof",
      }),
      ballotEncryptionKey,
    ),
  );
}

async function verifyZkProof(eid, candidateIds, encryptedVote, zkProof) {
  const candidateId = await decryptVote(eid, encryptedVote);
  if (!candidateIds.has(candidateId)) throw new Error("candidate is not in election candidate set");
  const expected = await makeZkProof(eid, candidateId, encryptedVote);
  if (zkProof !== expected) throw new Error("invalid zero-knowledge proof");
  return candidateId;
}

const tokenHashOf = (token) => sha256Hex(token);
const receiptHashOf = (ballotId, tokenHash) => sha256Hex(`${ballotId}|${tokenHash}`);

/* ============================================================
 * インメモリ・ストア（InMemoryRepository の JS 版）
 * ========================================================== */
function randomHex(byteLength) {
  return [...crypto.getRandomValues(new Uint8Array(byteLength))]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

function uuid4() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, "0"));
  return `${h.slice(0, 4).join("")}-${h.slice(4, 6).join("")}-${h.slice(6, 8).join("")}-${h
    .slice(8, 10)
    .join("")}-${h.slice(10, 16).join("")}`;
}

function bucket5Min(date) {
  const d = new Date(date.getTime());
  d.setUTCMinutes(d.getUTCMinutes() - (d.getUTCMinutes() % 5), 0, 0);
  return d.toISOString().replace(".000Z", "Z");
}

const store = {
  election: {
    election_id: electionId,
    title: "デモ選挙 2026",
    voter_salt: randomHex(16),
    status: "open",
    candidates: [
      { candidate_id: "cand-a", display_name: "候補者A", party: "未来党" },
      { candidate_id: "cand-b", display_name: "候補者B", party: "市民ネット" },
      { candidate_id: "cand-c", display_name: "候補者C", party: "無所属" },
    ],
  },
  voters: new Map(), // voter_hash -> { token_issued, revote_count }
  ballots: [], // public + internal fields
  ballotsByToken: new Map(),
  auditLogs: [],
  bucketSeq: new Map(),
};

function candidateIdSet() {
  return new Set(store.election.candidates.map((c) => c.candidate_id));
}

async function appendAudit(component, eventType, payload) {
  const prevHash = store.auditLogs.length
    ? store.auditLogs[store.auditLogs.length - 1].log_hash
    : "0".repeat(64);
  const occurredAt = new Date().toISOString();
  const material = canonicalBytes({
    component,
    event_type: eventType,
    occurred_at: occurredAt,
    payload,
    prev_hash: prevHash,
  });
  const entry = {
    log_id: store.auditLogs.length + 1,
    prev_hash: prevHash,
    log_hash: await sha256Hex(material),
    component,
    event_type: eventType,
    payload,
    occurred_at: occurredAt,
  };
  store.auditLogs.push(entry);
  return entry;
}

async function verifyAuditChain() {
  let prev = "0".repeat(64);
  for (const entry of store.auditLogs) {
    const material = canonicalBytes({
      component: entry.component,
      event_type: entry.event_type,
      occurred_at: entry.occurred_at,
      payload: entry.payload,
      prev_hash: prev,
    });
    const recomputed = await sha256Hex(material);
    if (entry.prev_hash !== prev || entry.log_hash !== recomputed) {
      return { valid: false, broken_at: entry.log_id, total: store.auditLogs.length };
    }
    prev = entry.log_hash;
  }
  return { valid: true, total: store.auditLogs.length, verified_from: 0, head_hash: prev };
}

function publicRecord(ballot) {
  return {
    ballot_id: ballot.ballot_id,
    election_id: ballot.election_id,
    blind_token_hash: ballot.blind_token_hash,
    received_at_bucket: ballot.received_at_bucket,
    sequence_in_bucket: ballot.sequence_in_bucket,
    revote_serial: ballot.revote_serial,
    receipt_hash: ballot.receipt_hash,
  };
}

/* ============================================================
 * サービス層（VotingService の JS 版）
 * ========================================================== */
function getVoter(voterHash) {
  if (!store.voters.has(voterHash)) {
    store.voters.set(voterHash, { token_issued: false, revote_count: 0 });
  }
  return store.voters.get(voterHash);
}

async function svcAuthenticate(certificateSerial, birthdate) {
  if (!certificateSerial || certificateSerial.length < 6) throw new Error("certificate_serial is invalid");
  if (!birthdate) throw new Error("birthdate is required for voter registry matching");
  const voterHash = await voterHashOf(certificateSerial, electionId, store.election.voter_salt);
  const voter = getVoter(voterHash);
  await appendAudit("jpki-gateway", "voter_authenticated", {
    election_id: electionId,
    voter_hash: voterHash,
    token_issued: voter.token_issued,
  });
  return { election_id: electionId, voter_hash: voterHash, eligible: true, token_issued: voter.token_issued, revote_count: voter.revote_count };
}

async function svcIssueToken(voterHash) {
  const voter = getVoter(voterHash);
  const serial = voter.revote_count + 1;
  const token = await issueTokenValue(electionId, voterHash, serial);
  const tokenHash = await tokenHashOf(token);
  voter.token_issued = true;
  voter.revote_count = serial;
  await appendAudit("blind-signer", "token_issued", { election_id: electionId, token_hash: tokenHash, revote_count: serial });
  return { election_id: electionId, blind_token: token, blind_token_hash: tokenHash, revote_count: serial };
}

async function svcPrepareVote(candidateId) {
  if (!candidateIdSet().has(candidateId)) throw new Error("candidate not found");
  const encryptedVote = await encryptVote(electionId, candidateId);
  const zkProof = await makeZkProof(electionId, candidateId, encryptedVote);
  return { encrypted_vote: encryptedVote, zk_proof: zkProof };
}

async function svcSubmitBallot(blindToken, encryptedVote, zkProof) {
  await verifyTokenValue(blindToken, electionId);
  const candidateId = await verifyZkProof(electionId, candidateIdSet(), encryptedVote, zkProof);
  const tokenHash = await tokenHashOf(blindToken);
  const ballotId = uuid4();
  const receiptHash = await receiptHashOf(ballotId, tokenHash);

  const nowBucket = bucket5Min(new Date());
  const seqKey = `${electionId}|${nowBucket}`;
  store.bucketSeq.set(seqKey, (store.bucketSeq.get(seqKey) || 0) + 1);
  const tokenBallots = store.ballotsByToken.get(tokenHash) || [];

  const ballot = {
    ballot_id: ballotId,
    election_id: electionId,
    blind_token_hash: tokenHash,
    encrypted_vote: encryptedVote,
    zk_proof: zkProof,
    received_at_bucket: nowBucket,
    sequence_in_bucket: store.bucketSeq.get(seqKey),
    revote_serial: tokenBallots.length + 1,
    receipt_hash: receiptHash,
    accepted_candidate_id: candidateId,
  };
  store.ballots.push(ballot);
  tokenBallots.push(ballotId);
  store.ballotsByToken.set(tokenHash, tokenBallots);
  await appendAudit("ballot-box", "ballot_accepted", {
    ballot_id: ballotId,
    election_id: electionId,
    receipt_hash: receiptHash,
    token_hash: tokenHash,
  });
  return publicRecord(ballot);
}

async function svcTally() {
  const latestByToken = new Map();
  for (const ballot of store.ballots) {
    const current = latestByToken.get(ballot.blind_token_hash);
    if (!current || ballot.revote_serial > current.revote_serial) {
      latestByToken.set(ballot.blind_token_hash, ballot);
    }
  }
  const counts = {};
  for (const c of store.election.candidates) counts[c.candidate_id] = 0;
  for (const ballot of latestByToken.values()) counts[ballot.accepted_candidate_id] += 1;
  const result = { election_id: electionId, accepted_ballots: latestByToken.size, counts };
  await appendAudit("tally", "tally_computed", result);
  return result;
}

async function svcVerifyReceipt(receiptHash) {
  if (!/^[0-9a-f]{64}$/.test(receiptHash)) throw new Error("receipt_hash must be a 64-character lowercase hex string");
  const ballot = store.ballots.find((b) => b.receipt_hash === receiptHash);
  if (!ballot) return { found: false, receipt_hash: receiptHash };
  const recomputed = await receiptHashOf(ballot.ballot_id, ballot.blind_token_hash);
  return {
    found: true,
    receipt_hash: receiptHash,
    recomputed_receipt_hash: recomputed,
    integrity_ok: recomputed === receiptHash,
    ballot: publicRecord(ballot),
  };
}

function svcMetrics() {
  return {
    elections: [{ election_id: electionId, status: store.election.status, ballots_recorded: store.ballots.length }],
    total_elections: 1,
    total_ballots_recorded: store.ballots.length,
    audit_log_entries: store.auditLogs.length,
  };
}

/* ============================================================
 * モックルーター（client-web の fetch を置き換える api 相当）
 * ========================================================== */
async function mockApi(path, options = {}) {
  const method = (options.method || "GET").toUpperCase();
  const body = options.body ? JSON.parse(options.body) : {};
  const base = `/elections/${electionId}`;

  if (method === "GET" && path === base) {
    return { ...store.election };
  }
  if (method === "POST" && path === `${base}/authenticate`) {
    return svcAuthenticate(body.certificate_serial, body.birthdate);
  }
  if (method === "POST" && path === `${base}/issue-token`) {
    return svcIssueToken(body.voter_hash);
  }
  if (method === "POST" && path === `${base}/prepare-vote`) {
    return svcPrepareVote(body.candidate_id);
  }
  if (method === "POST" && path === `${base}/ballots`) {
    return svcSubmitBallot(body.blind_token, body.encrypted_vote, body.zk_proof);
  }
  if (method === "GET" && path === `${base}/bulletin-board`) {
    return { election_id: electionId, ballots: store.ballots.map(publicRecord) };
  }
  if (method === "GET" && path.startsWith(`${base}/receipts/`)) {
    const hash = decodeURIComponent(path.slice(`${base}/receipts/`.length));
    return svcVerifyReceipt(hash);
  }
  if (method === "GET" && path === `${base}/tally`) {
    return svcTally();
  }
  if (method === "GET" && path === "/audit-log") {
    return { audit_log: store.auditLogs.map((e) => ({ ...e })) };
  }
  if (method === "GET" && path === "/audit-log/verify") {
    return verifyAuditChain();
  }
  if (method === "GET" && path === "/metrics") {
    return svcMetrics();
  }
  throw new Error(`未対応のデモ操作です: ${method} ${path}`);
}

// client-web/main.js の api() を、ネットワークを介さないモックに差し替える。
function api(path, options = {}) {
  return mockApi(path, options);
}

/* ============================================================
 * 以下は client-web/main.js の UI ロジックを移植
 * （api() がモックを指す以外は同一の挙動）
 * ========================================================== */
let voterHash = "";
let selectedCandidate = "";
let candidateCache = [];
let lastReceiptHash = "";
let boardCache = [];
const candidateColors = ["#2f7d6d", "#a7563f", "#5d6fb1", "#8a6d2f", "#6f5a8f", "#35708a"];

const $ = (id) => document.getElementById(id);

function setLiveSeverity(el, isError) {
  if (!el) return;
  el.setAttribute("aria-live", isError ? "assertive" : "polite");
  el.setAttribute("role", isError ? "alert" : "status");
}

function announce(el, message, isError = false) {
  if (!el) return;
  setLiveSeverity(el, isError);
  if ("value" in el && el.tagName === "OUTPUT") {
    el.value = message;
  } else {
    el.textContent = message;
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderCandidates(candidates) {
  candidateCache = candidates;
  $("candidates").innerHTML = candidates
    .map(
      (candidate) => `
        <label class="candidate" style="--candidate-color: ${candidateColor(candidate.candidate_id)}">
          <input type="radio" name="candidate" value="${candidate.candidate_id}">
          <span>
            <strong>${escapeHtml(candidate.display_name)}</strong>
            <span>${escapeHtml(candidate.party || "無所属")}</span>
          </span>
        </label>
      `,
    )
    .join("");

  document.querySelectorAll("input[name='candidate']").forEach((input) => {
    input.addEventListener("change", () => {
      selectedCandidate = input.value;
      $("voteButton").disabled = !voterHash || !selectedCandidate;
      announce($("voteStatus"), voterHash ? "投票準備ができました" : "先に本人確認を行ってください");
    });
  });
}

function candidateColor(candidateId) {
  const index = Math.max(0, candidateCache.findIndex((candidate) => candidate.candidate_id === candidateId));
  return candidateColors[index % candidateColors.length];
}

function candidateLabel(candidateId) {
  const candidate = candidateCache.find((item) => item.candidate_id === candidateId);
  return candidate ? candidate.display_name : candidateId;
}

async function loadElection() {
  const election = await api(`/elections/${electionId}`);
  document.querySelector("h1").textContent = election.title;
  renderCandidates(election.candidates);
  await refreshBoard();
}

async function authenticate() {
  announce($("authStatus"), "認証中...");
  const result = await api(`/elections/${electionId}/authenticate`, {
    method: "POST",
    body: JSON.stringify({
      certificate_serial: $("certificateSerial").value,
      birthdate: $("birthdate").value,
    }),
  });
  voterHash = result.voter_hash;
  announce($("authStatus"), `認証済み / 再発行回数 ${result.revote_count}`);
  $("voteButton").disabled = !selectedCandidate;
}

async function vote() {
  if (!voterHash) {
    announce($("voteStatus"), "先に本人確認を行ってください", true);
    return;
  }
  announce($("voteStatus"), "投票券発行中...");
  const token = await api(`/elections/${electionId}/issue-token`, {
    method: "POST",
    body: JSON.stringify({ voter_hash: voterHash }),
  });
  announce($("voteStatus"), "暗号化中...");
  const prepared = await api(`/elections/${electionId}/prepare-vote`, {
    method: "POST",
    body: JSON.stringify({ candidate_id: selectedCandidate }),
  });
  announce($("voteStatus"), "送信中...");
  const receipt = await api(`/elections/${electionId}/ballots`, {
    method: "POST",
    body: JSON.stringify({
      blind_token: token.blind_token,
      encrypted_vote: prepared.encrypted_vote,
      zk_proof: prepared.zk_proof,
    }),
  });
  lastReceiptHash = receipt.receipt_hash;
  announce($("voteStatus"), `受領証: ${receipt.receipt_hash}`);
  $("receiptInput").value = receipt.receipt_hash;
  await refreshBoard();
}

async function verifyReceipt() {
  const input = $("receiptInput");
  const resultEl = $("receiptResult");
  const hash = input.value.trim();
  if (!hash) {
    input.setAttribute("aria-invalid", "true");
    input.setAttribute("aria-describedby", "receiptHint receiptResult");
    setLiveSeverity(resultEl, true);
    resultEl.innerHTML = '<div class="status warning">receipt_hash を入力してください</div>';
    return;
  }
  input.removeAttribute("aria-invalid");
  input.setAttribute("aria-describedby", "receiptHint");
  const result = await api(`/elections/${electionId}/receipts/${encodeURIComponent(hash)}`);
  if (!result.found) {
    setLiveSeverity(resultEl, true);
    resultEl.innerHTML = `
      <div class="status danger">
        <strong>未掲載</strong>
        <span>${escapeHtml(result.receipt_hash)}</span>
      </div>
    `;
    return;
  }
  setLiveSeverity(resultEl, !result.integrity_ok);
  resultEl.innerHTML = `
    <div class="status ${result.integrity_ok ? "ok" : "danger"}">
      <strong>${result.integrity_ok ? "掲載済み / 整合性OK" : "掲載済み / 整合性NG"}</strong>
      <span>${escapeHtml(result.receipt_hash)}</span>
      <small>ballot_id: ${escapeHtml(result.ballot.ballot_id)}</small>
      <small>received_at_bucket: ${escapeHtml(result.ballot.received_at_bucket)}</small>
    </div>
  `;
}

async function verifyAudit() {
  const result = await api(`/audit-log/verify`);
  $("auditResult").textContent = JSON.stringify(result, null, 2);
}

async function loadMetrics() {
  const result = await api(`/metrics`);
  $("metricsResult").textContent = JSON.stringify(result, null, 2);
}

async function loadAuditLog() {
  const result = await api(`/audit-log`);
  const entries = result.audit_log.slice(-12).reverse();
  $("auditLogTable").innerHTML =
    entries
      .map(
        (entry) => `
          <div class="row">
            <span>${escapeHtml(entry.log_id)}</span>
            <span>${escapeHtml(entry.component)}</span>
            <span>${escapeHtml(entry.event_type)}</span>
            <span>${escapeHtml(entry.log_hash.slice(0, 12))}</span>
          </div>
        `,
      )
      .join("") || "<p>監査ログはまだありません。</p>";
}

function renderBoard() {
  const filter = $("boardFilter").value.trim().toLowerCase();
  const ballots = filter
    ? boardCache.filter((ballot) => ballot.receipt_hash.toLowerCase().includes(filter))
    : boardCache;
  $("bulletinBoard").innerHTML =
    ballots
      .map(
        (ballot) => `
          <div class="record">
            <strong>${escapeHtml(ballot.ballot_id)}</strong>
            <span>${escapeHtml(ballot.receipt_hash)}</span>
          </div>
        `,
      )
      .join("") || "<p>該当する投票記録はありません。</p>";
}

async function refreshBoard() {
  const board = await api(`/elections/${electionId}/bulletin-board`);
  boardCache = board.ballots;
  renderBoard();
}

async function tally() {
  const result = await api(`/elections/${electionId}/tally`);
  renderTally(result);
}

function renderTally(result) {
  const entries = Object.entries(result.counts);
  const maxVotes = Math.max(1, ...entries.map(([, count]) => count));
  $("tally").innerHTML = `
    <div class="tally-summary">
      <strong>有効票 ${escapeHtml(result.accepted_ballots)}</strong>
      <span>${escapeHtml(result.election_id)}</span>
    </div>
    <div class="tally-bars">
      ${entries
        .map(([candidateId, count]) => {
          const width = Math.round((count / maxVotes) * 100);
          return `
            <div class="tally-row" style="--candidate-color: ${candidateColor(candidateId)}">
              <div class="tally-label">
                <strong>${escapeHtml(candidateLabel(candidateId))}</strong>
                <span>${escapeHtml(candidateId)}</span>
              </div>
              <div class="bar-track">
                <div class="bar-fill" style="width: ${width}%"></div>
              </div>
              <strong class="vote-count">${escapeHtml(count)}</strong>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

// デモを開いた瞬間から掲示板・集計が見えるよう、少数の票を内部フローで投じておく。
async function seedDemoBallots(rounds = 7) {
  const ids = store.election.candidates.map((c) => c.candidate_id);
  for (let i = 0; i < rounds; i += 1) {
    const auth = await svcAuthenticate(`CERT-SEED-${String(i).padStart(6, "0")}`, "1980-01-01");
    const token = await svcIssueToken(auth.voter_hash);
    const candidate = ids[Math.floor((i * 7 + 3) % ids.length)];
    const prepared = await svcPrepareVote(candidate);
    await svcSubmitBallot(token.blind_token, prepared.encrypted_vote, prepared.zk_proof);
  }
}

$("authButton").addEventListener("click", () => authenticate().catch((error) => announce($("authStatus"), error.message, true)));
$("voteButton").addEventListener("click", () => vote().catch((error) => announce($("voteStatus"), error.message, true)));
$("refreshButton").addEventListener("click", () => refreshBoard().catch((error) => announce($("bulletinBoard"), error.message, true)));
$("tallyButton").addEventListener("click", () => tally().catch((error) => announce($("tally"), error.message, true)));
$("receiptButton").addEventListener("click", () => verifyReceipt().catch((error) => {
  setLiveSeverity($("receiptResult"), true);
  $("receiptResult").innerHTML = `<div class="status danger">${escapeHtml(error.message)}</div>`;
}));
$("auditButton").addEventListener("click", () => verifyAudit().catch((error) => announce($("auditResult"), error.message, true)));
$("auditLogButton").addEventListener("click", () => loadAuditLog().catch((error) => announce($("auditLogTable"), error.message, true)));
$("metricsButton").addEventListener("click", () => loadMetrics().catch((error) => announce($("metricsResult"), error.message, true)));
$("boardFilter").addEventListener("input", renderBoard);

seedDemoBallots()
  .catch(() => {})
  .finally(() => {
    loadElection().catch((error) => announce($("authStatus"), error.message, true));
  });
