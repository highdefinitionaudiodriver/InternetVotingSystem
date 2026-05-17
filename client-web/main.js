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
    if (!response.ok) throw new Error(data.error || response.statusText);
    return data;
  });
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
  $("voteStatus").value = `受領証: ${receipt.receipt_hash}`;
  await refreshBoard();
}

async function refreshBoard() {
  const board = await api(`/elections/${electionId}/bulletin-board`);
  $("bulletinBoard").innerHTML =
    board.ballots
      .map(
        (ballot) => `
          <div class="record">
            <strong>${ballot.ballot_id}</strong>
            <span>${ballot.receipt_hash}</span>
          </div>
        `,
      )
      .join("") || "<p>まだ投票記録はありません。</p>";
}

async function tally() {
  const result = await api(`/elections/${electionId}/tally`);
  $("tally").textContent = JSON.stringify(result, null, 2);
}

$("authButton").addEventListener("click", () => authenticate().catch((error) => ($("authStatus").value = error.message)));
$("voteButton").addEventListener("click", () => vote().catch((error) => ($("voteStatus").value = error.message)));
$("refreshButton").addEventListener("click", () => refreshBoard().catch((error) => ($("bulletinBoard").textContent = error.message)));
$("tallyButton").addEventListener("click", () => tally().catch((error) => ($("tally").textContent = error.message)));

loadElection().catch((error) => {
  $("authStatus").value = error.message;
});
