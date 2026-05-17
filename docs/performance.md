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
