# Operations Runbook

最終更新: 2026-05-17 (Claude Code セッション 5)

このドキュメントは、本プロトタイプを開発/評価環境で運用する際の手順をまとめます。本番運用は別途、暗号差し替え・PostgreSQL化・JPKI実接続・WORM監査基盤が必要です。

---

## 1. ストレージ・バックエンドの選択

| バックエンド | 用途 | 起動コマンド |
|---|---|---|
| `memory` | デモ・テスト | `python -m internet_voting_system.app --storage memory` |
| `sqlite` | 単一ホスト永続化 | `python -m internet_voting_system.app --storage sqlite --sqlite-path voting.sqlite3` |
| `postgres` | 多ホスト本番想定 | `python -m internet_voting_system.app --storage postgres --dsn postgresql://user:pw@host:5432/voting` |

`postgres` を選ぶ場合は事前に次を行ってください。

```bash
# 1. データベース作成
createdb voting

# 2. スキーマ適用
psql -v ON_ERROR_STOP=1 -d voting \
  -f services/api/internet_voting_system/sql/postgresql_schema.sql

# 3. 必須Pythonパッケージ
pip install 'psycopg[binary]>=3.1'
```

PostgresRepository は `psycopg` が import できない環境では起動時に明確な `RuntimeError` を出します。

---

## 2. メトリクス取得

`/metrics` は2つの形式に対応します。

### JSON（デフォルト、Webクライアントや自前ダッシュボード向け）

```bash
curl -s http://127.0.0.1:8787/metrics | jq
```

### Prometheus テキスト形式

`?format=prometheus` か `Accept: text/plain` のどちらかで切り替わります。

```bash
curl -s -H 'Accept: text/plain' http://127.0.0.1:8787/metrics
```

```text
# HELP internet_voting_total_elections Number of elections registered in this API.
# TYPE internet_voting_total_elections gauge
internet_voting_total_elections 1
# HELP internet_voting_total_ballots_recorded Total ballots stored across all elections.
# TYPE internet_voting_total_ballots_recorded counter
internet_voting_total_ballots_recorded 42
# HELP internet_voting_audit_log_entries Number of hash-chained audit log entries.
# TYPE internet_voting_audit_log_entries counter
internet_voting_audit_log_entries 128
# HELP internet_voting_election_ballots Ballots recorded per election.
# TYPE internet_voting_election_ballots gauge
internet_voting_election_ballots{election_id="demo-2026",status="open"} 42
```

### Prometheus scrape 設定例

```yaml
scrape_configs:
  - job_name: internet-voting-system
    metrics_path: /metrics
    scrape_interval: 30s
    static_configs:
      - targets:
          - "ivs-api.internal:8787"
    params:
      format: ["prometheus"]   # 念のため query param でも要求しておく
```

**プライバシ保証**: `/metrics` は集計値のみを返します。`voter_hash`、`ballot_id`、`receipt_hash`、候補別カウント、監査ログ本文は一切含まれません。`tests/test_metrics_and_shutdown.py::test_metrics_summary_does_not_leak_identity_or_candidate_counts` と `test_prometheus_and_postgres.py::test_prometheus_output_does_not_leak_identity` が継続的に検証します。

---

## 3. 監査ログ整合性チェック

```bash
curl -s http://127.0.0.1:8787/audit-log/verify | jq
```

`{"valid": true, "total": <count>, "head_hash": "<sha256>"}` が返れば、Audit ハッシュチェーンに改ざんはありません。`valid: false` の場合は `broken_at` に最初に破綻したレコードの `log_id` が入ります。

cron で定期実行してアラートに繋げる場合の例:

```bash
*/5 * * * * /usr/bin/curl -fsS http://127.0.0.1:8787/audit-log/verify \
  | jq -e '.valid == true' >/dev/null \
  || /usr/local/bin/alert-fire "ivs audit chain broken"
```

---

## 4. graceful shutdown

API サーバは SIGINT / SIGTERM / SIGBREAK を捕捉して `ThreadingHTTPServer.shutdown()` を呼びます。`docker stop` が送る SIGTERM、Kubernetes の `preStop` が送る SIGTERM、Ctrl+C の SIGINT、いずれも同じ経路で接続を排出してから終了します。

ログ上 `ivs-shutdown` という名前の daemon thread が `server.shutdown()` を呼ぶのを確認できます。

---

## 5. スモーク検証

API 起動後、別ターミナルから:

```bash
python tools/smoke_check.py --base-url http://127.0.0.1:8787
```

成功すると次の形式の JSON を返します。

```json
{
  "status": "ok",
  "election_id": "demo-2026",
  "candidate_id": "cand-a",
  "ballot_id": "...",
  "receipt_hash": "...",
  "audit_head_hash": "...",
  "total_ballots_recorded": 1
}
```

`/metrics` の値もチェックに含まれているので、メトリクス側だけ壊れる回帰も検出できます。

---

## 6. 負荷試験

```bash
python tools/loadtest.py \
  --base-url http://127.0.0.1:8787 \
  --voters 500 --concurrency 50 \
  --verify-receipts
```

詳細は `docs/performance.md` を参照。

---

## 7. Docker Compose 運用

```bash
# 揮発
docker compose --profile memory up --build

# SQLite 永続化（推奨ボリューム: vote-data）
docker compose --profile sqlite up --build
```

Web クライアントは常時 `http://localhost:8788`、API は `http://localhost:8787` に出ます。
ボリュームの中身をバックアップする場合:

```bash
docker run --rm -v ivs_vote-data:/data -v $PWD:/backup alpine \
  tar czf /backup/vote-data-$(date -u +%Y%m%dT%H%M%SZ).tgz -C /data .
```

---

## 8. インシデント対応プレイブック

| シグナル | 想定原因 | 一次対応 |
|---|---|---|
| `/audit-log/verify` が `valid: false` | DB改ざん / 同期事故 | API を即時停止、最後のスナップショットから復元、`broken_at` 以降を再生成 |
| `/health` が 500 系 | アプリ起動失敗 | コンテナログ確認、ストレージ DSN 確認 |
| `internet_voting_total_ballots_recorded` が想定外に増加 | 二重投票 or 不正リクエスト | 受付ログを `audit_log` テーブルで時系列確認、`blind_token_hash` 重複の有無を確認 |
| 受領証検証で `integrity_ok: false` | 票内容の事後改変疑い | 即座に当該 ballot を保全し、ミックスネット投入を停止 |
| `tools/loadtest.py` で `success` が `voters` を下回る | スループット飽和 | 並列度を下げる、ストレージを `memory` → `sqlite` → `postgres` に切替えて再計測 |
