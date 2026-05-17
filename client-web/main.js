const electionId = "demo-2026";
let voterHash = "";
let selectedCandidate = "";

const $ = (id) => document.getElementById(id);

function api(path, options = {}) {
  const base = $("apiBase").value.replace(/\/$/, "");
  return fetch(`${base}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  }).then(async (response) => {
    const data = await response.json();
    if (!response.ok) {
      // Standardised error envelope is { error: { code, message } }.
      const message =
        (data && data.error && (data.error.message || data.error)) ||
        response.statusText;
      throw new Error(typeof message === "string" ? message : JSON.stringify(message));
    }
    return data;
  });
}

let lastReceiptHash = "";
let boardCache = [];

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderCandidates(candidates) {
  $("candidates").innerHTML = candidates
    .map(
      (candidate) => `
        <label class="candidate">
          <input type="radio" name="candidate" value="${candidate.candidate_id}">
          <span>
            <strong>${candidate.display_name}</strong>
            <span>${candidate.party || "無所属"}</span>
          </span>
        </label>
      `,
    )
    .join("");

  document.querySelectorAll("input[name='candidate']").forEach((input) => {
    input.addEventListener("change", () => {
      selectedCandidate = input.value;
      $("voteButton").disabled = !voterHash || !selectedCandidate;
      $("voteStatus").value = "投票準備ができました";
    });
  });
}

async function loadElection() {
  const election = await api(`/elections/${electionId}`);
  document.querySelector("h1").textContent = election.title;
  renderCandidates(election.candidates);
  await refreshBoard();
}

async function authenticate() {
  $("authStatus").value = "認証中...";
  const result = await api(`/elections/${electionId}/authenticate`, {
    method: "POST",
    body: JSON.stringify({
      certificate_serial: $("certificateSerial").value,
      birthdate: $("birthdate").value,
    }),
  });
  voterHash = result.voter_hash;
  $("authStatus").value = `認証済み / 再発行回数 ${result.revote_count}`;
  $("voteButton").disabled = !selectedCandidate;
}

async function vote() {
  $("voteStatus").value = "投票券発行中...";
  const token = await api(`/elections/${electionId}/issue-token`, {
    method: "POST",
    body: JSON.stringify({ voter_hash: voterHash }),
  });
  $("voteStatus").value = "暗号化中...";
  const prepared = await api(`/elections/${electionId}/prepare-vote`, {
    method: "POST",
    body: JSON.stringify({ candidate_id: selectedCandidate }),
  });
  $("voteStatus").value = "送信中...";
  const receipt = await api(`/elections/${electionId}/ballots`, {
    method: "POST",
    body: JSON.stringify({
      blind_token: token.blind_token,
      encrypted_vote: prepared.encrypted_vote,
      zk_proof: prepared.zk_proof,
    }),
  });
  lastReceiptHash = receipt.receipt_hash;
  $("voteStatus").value = `受領証: ${receipt.receipt_hash}`;
  $("receiptInput").value = receipt.receipt_hash;
  await refreshBoard();
}

async function verifyReceipt() {
  const hash = $("receiptInput").value.trim();
  if (!hash) {
    $("receiptResult").innerHTML = '<div class="status warning">receipt_hash を入力してください</div>';
    return;
  }
  const result = await api(`/elections/${electionId}/receipts/${encodeURIComponent(hash)}`);
  if (!result.found) {
    $("receiptResult").innerHTML = `
      <div class="status danger">
        <strong>未掲載</strong>
        <span>${escapeHtml(result.receipt_hash)}</span>
      </div>
    `;
    return;
  }
  $("receiptResult").innerHTML = `
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
  $("tally").textContent = JSON.stringify(result, null, 2);
}

$("authButton").addEventListener("click", () => authenticate().catch((error) => ($("authStatus").value = error.message)));
$("voteButton").addEventListener("click", () => vote().catch((error) => ($("voteStatus").value = error.message)));
$("refreshButton").addEventListener("click", () => refreshBoard().catch((error) => ($("bulletinBoard").textContent = error.message)));
$("tallyButton").addEventListener("click", () => tally().catch((error) => ($("tally").textContent = error.message)));
$("receiptButton").addEventListener("click", () => verifyReceipt().catch((error) => ($("receiptResult").innerHTML = `<div class="status danger">${escapeHtml(error.message)}</div>`)));
$("auditButton").addEventListener("click", () => verifyAudit().catch((error) => ($("auditResult").textContent = error.message)));
$("auditLogButton").addEventListener("click", () => loadAuditLog().catch((error) => ($("auditLogTable").textContent = error.message)));
$("boardFilter").addEventListener("input", renderBoard);

loadElection().catch((error) => {
  $("authStatus").value = error.message;
});
