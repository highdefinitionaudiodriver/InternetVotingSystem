# Performance Notes

最終更新: 2026-05-17

## 目的

`tools/loadtest.py` を使い、プロトタイプAPIのフルフローが並列実行できることを確認する。

対象フロー:

0. `GET /elections/{id}` で候補者IDを取得
1. `POST /elections/{id}/authenticate`
2. `POST /elections/{id}/issue-token`
3. `POST /elections/{id}/prepare-vote`
4. `POST /elections/{id}/ballots`
5. `GET /elections/{id}/receipts/{receipt_hash}` (`--verify-receipts` 指定時)

## 2026-05-17 メモリストレージ baseline

実行条件:

```powershell
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools\loadtest.py --base-url http://127.0.0.1:8787 --voters 20 --concurrency 4 --verify-receipts
```

API起動条件:

```powershell
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m internet_voting_system.app --host 127.0.0.1 --port 8787 --storage memory
```

結果:

```json
{
  "success": 20,
  "failed": 0,
  "throughput_flows_per_second": 206.17,
  "latency_ms": {
    "min": 9.55,
    "median": 16.25,
    "p95": 25.21,
    "max": 31.27
  }
}
```

## 注意

この値は開発PC上の小規模スモーク負荷試験であり、実運用性能を示すものではない。標準ライブラリHTTPサーバー、デモ暗号、インメモリRepositoryのため、ネットワーク分離・永続化・本番暗号・監査基盤を含む性能とは別物として扱う。

## 2026-05-17 SQLiteストレージ baseline

実行条件:

```powershell
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools\loadtest.py --base-url http://127.0.0.1:8789 --voters 20 --concurrency 4 --verify-receipts
```

API起動条件:

```powershell
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m internet_voting_system.app --host 127.0.0.1 --port 8789 --storage sqlite --sqlite-path loadtest.sqlite3
```

結果:

```json
{
  "success": 20,
  "failed": 0,
  "throughput_flows_per_second": 52.62,
  "latency_ms": {
    "min": 49.85,
    "median": 72.7,
    "p95": 97.46,
    "max": 121.7
  }
}
```

SQLiteストレージは単一ホスト永続化の確認用であり、書き込みは直列化される。今回の小規模測定でもメモリストレージよりスループットが大きく低下した。本番相当の並行負荷試験はPostgreSQLバックエンド実装後に再計測する。

## 2026-05-17 メモリストレージ スケール拡張

開発PC上での上限把握のため、`voters` と `concurrency` を引き上げた結果。

### 200 voters / concurrency 20 (`--verify-receipts`)

API起動:

```powershell
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m internet_voting_system.app --host 127.0.0.1 --port 8790 --storage memory
```

実行:

```powershell
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools\loadtest.py --base-url http://127.0.0.1:8790 --voters 200 --concurrency 20 --verify-receipts
```

結果:

```json
{
  "success": 200,
  "failed": 0,
  "elapsed_seconds": 1.754,
  "throughput_flows_per_second": 114.03,
  "latency_ms": { "min": 13.30, "median": 31.41, "p95": 718.58, "max": 1539.69 }
}
```

### 500 voters / concurrency 50 (`--verify-receipts`)

```json
{
  "success": 500,
  "failed": 0,
  "elapsed_seconds": 4.647,
  "throughput_flows_per_second": 107.60,
  "latency_ms": { "min": 17.18, "median": 42.32, "p95": 2098.44, "max": 4131.88 }
}
```

### 観察

- スループットは並行度を上げても 100〜120 flows/sec で頭打ちになる。標準ライブラリ `ThreadingHTTPServer` の GIL ボトルネックが支配的とみられる。
- 並行度が上がるにつれ p95/max が急増し、200 voters → 500 voters で max が約 1.5s → 4.1s に拡大した。これは TCP/HTTP の処理キューが満ちて並列ワーカーが待たされている兆候。
- 失敗はゼロのまま。標準ライブラリ HTTP + メモリストレージでも、整合性は保たれている。
- 本番想定の数値は、FastAPI + uvicorn + PostgreSQL に置き換えた後に再計測すること。本ファイルの数値はあくまでもプロトタイプの傾向把握用とする。
