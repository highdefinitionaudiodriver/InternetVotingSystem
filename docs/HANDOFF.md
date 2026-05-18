# Claude Code / Codex 引き継ぎ資料

最終更新: 2026-05-18 (Claude Code セッション 6 終了時)

## 作業場所

今後の主作業場所は次のGitHub作業ツリーとする。

```text
C:\Users\highd\Documents\Github\InternetVotingSystem
```

作業完了後、コミット・プッシュした差分成果物を次の設計・成果物保管先へ同期する。

```text
G:\マイドライブ\claudecode\InternetVotingSystem
```

## 基本手順

1. `C:\Users\highd\Documents\Github\InternetVotingSystem` で実装・修正する。
2. テストを実行し、差分を確認する。
3. GitHub作業ツリーでコミットする。
4. `origin/main` へプッシュする。
5. コミット済み成果物を `G:\マイドライブ\claudecode\InternetVotingSystem` へ同期する。

## 現在の実装状況（セッション 2 終了時点）

### 構成

- APIサーバー: `services/api/internet_voting_system/app.py`
  - `--storage memory|sqlite` で永続化バックエンドを切替可能
  - `--sqlite-path` でSQLiteファイルパス指定
- ドメインサービス: `services/api/internet_voting_system/service.py`
- デモ暗号境界: `services/api/internet_voting_system/crypto.py`
- Repositoryプロトコル: `services/api/internet_voting_system/repository_base.py` （NEW）
  - `@runtime_checkable` 化し、`VotingService` の型注釈も `Repository` へ変更（Codex セッション9）
- インメモリRepository: `services/api/internet_voting_system/repository.py`
- SQLite Repository: `services/api/internet_voting_system/sqlite_repository.py` （NEW）
- Webクライアント: `client-web/`
  - 受領証検証パネル・監査ログ整合性チェックパネルを追加
  - 公開掲示板のreceipt_hash部分一致フィルター、監査ログ直近テーブル表示を追加（Codex セッション4）
  - 受領証検証結果をJSON表示から状態ラベル表示へ変更（Codex セッション5）
  - 候補者カードの色分け、集計プレビューの候補者別バー表示を追加（Codex セッション6）
  - 候補者名・政党名などAPI由来表示値のHTMLエスケープを追加（Codex セッション6）
- API定義: `docs/api/openapi.yaml`
  - 全エンドポイントのレスポンススキーマ追加
  - エラー応答 `{error:{code,message}}` 統一スキーマ追加
- テスト: `services/api/tests/`
  - `test_voting_service.py` （既存4件）
  - `test_audit_and_receipts.py` （NEW、4件）
  - `test_sqlite_repository.py` （NEW、5件）
  - `test_openapi_privacy_lint.py` （Codex セッション4で追加、3件）
  - `test_loadtest_tool.py` （Codex セッション7で追加、2件）
  - `test_http_api.py` （Codex セッション8で追加、5件）
  - `test_repository_protocol.py` （Codex セッション9で追加、2件）
  - `test_smoke_check_tool.py` （Codex セッション10で追加、1件）
  - `test_metrics_and_shutdown.py` （Claude Code セッション 4 で追加、4件）
  - `test_prometheus_and_postgres.py` （Claude Code セッション 5 で追加、5件）
  - `test_postgres_integration.py` （Claude Code セッション 6 で追加、4件。`IVS_TEST_PG_DSN` 設定時のみ実行）
  - 計40件（DSN未設定では postgres 4件スキップ、残り36件すべてパス）
- スモークチェック: `tools/smoke_check.py` （Codex セッション10で追加）
  - 起動済みAPIに対して health、投票フロー、受領証検証、監査ログ整合性を単発確認
  - CIの構文チェック対象にも追加済み
- ローカル統合チェック: `tools/check_all.py` （Codex セッション13で追加）
  - APIユニットテスト、OpenAPIプライバシーlint、Web JS構文、standalone tools構文を一括実行
  - `.github/workflows/ci.yml` もこのツールを呼ぶ形へ変更し、ローカルとCIの実行内容を揃えた
- 負荷試験: `tools/loadtest.py` （Codex セッション3で追加）
  - 標準ライブラリのみで `authenticate -> issue-token -> prepare-vote -> ballots` のフルフローを並列実行
  - `--verify-receipts` 指定時は受領証検証エンドポイントまで確認
  - 候補者IDを `GET /elections/{id}` から取得するよう変更（Codex セッション7）
- 性能メモ: `docs/performance.md` （Codex セッション3で追加）
  - メモリ/SQLiteストレージで `--voters 20 --concurrency 4 --verify-receipts` のスモーク負荷試験結果を記録
  - Claude Code セッション 3 で 200/500 voters のスケール拡張結果を追記。スループットは 100〜120 flows/sec で頭打ち、p95/maxは並行度増加で急増（GIL+標準ライブラリHTTPサーバー起因と推測）
- コンテナ化: `Dockerfile`, `Dockerfile.web`, `docker-compose.yml` （Claude Code セッション 3 で追加）
  - APIコンテナは Python 3.12-slim ベース、非rootユーザー実行、依存ゼロ
  - Web静的配信は nginx:alpine ベース
  - `docker compose --profile memory up --build` または `--profile sqlite up --build` で起動
  - SQLiteプロファイルは名前付きボリューム `vote-data` を `/data` にマウント
- Graceful shutdown: `app.py` の `install_graceful_shutdown()` （Claude Code セッション 4 で追加）
  - SIGINT / SIGTERM / SIGBREAK を捕捉し、`server.shutdown()` を別スレッドから呼ぶ
  - Windows では SIGTERM が無効だが try/except で握り潰すため移植可能
- 運用メトリクスエンドポイント: `GET /metrics` （Claude Code セッション 4 で追加、セッション 5 で Prometheus 形式並行対応）
  - 総選挙数、選挙別ballot数、監査ログエントリ数のみ返す
  - 候補者別集計（counts）や個別票情報は含めず、監視スクレーパが安全に取得できる
  - Webクライアントの「運用メトリクス」パネル、`tools/smoke_check.py` でも検査
  - `?format=prometheus` または `Accept: text/plain` で Prometheus text exposition format（`version=0.0.4`）を返す
  - `VotingService.metrics_prometheus()` がラベルエスケープを含めて整形
- PostgreSQLスキーマ: `services/api/internet_voting_system/sql/postgresql_schema.sql` （Claude Code セッション 4 で追加）
  - `voting` スキーマ配下に elections / candidates / voter_status / ballot / audit_log を定義
  - SQLite版とロジカルモデルを一致させてある（差分レビュー容易）
  - 推奨ロール（jpki_gateway / blind_signer / ballot_box / tally）の最小権限GRANT文をコメントで提示
- PostgreSQLリポジトリ実装: `services/api/internet_voting_system/postgres_repository.py` （Claude Code セッション 5 で追加）
  - `psycopg` (3.x) を遅延 import。未インストール環境では明確な `RuntimeError`
  - SQLite版と同等の API、`SELECT ... FOR UPDATE` でトークン発行を直列化
  - JSONB カラム (`encrypted_vote`, `payload`) は `%s::jsonb` キャストで投入
  - **CI未テスト**（libpq不要のためubuntuランナーでCIを組むのは可能、優先タスク参照）
- `app.py --storage postgres --dsn ...` を新規追加（Claude Code セッション 5）
- docker build CI: `.github/workflows/ci.yml` に `docker-build` ジョブ追加（Claude Code セッション 4）
  - ubuntu-latest 上で API/Web イメージをビルドし、APIコンテナを起動して `tools/smoke_check.py` を回す
  - セッション 5 で Prometheus 形式の `/metrics` レスポンス確認も追加
- docker compose smoke CI: `.github/workflows/ci.yml` に `compose-smoke` ジョブ追加（Claude Code セッション 5）
  - `docker compose --profile sqlite up -d --build` で API + Web + ボリュームを起動
  - API `/health`、Web `/`、`tools/smoke_check.py` をまとめて検証
  - 終了時に `docker compose down --volumes` で完全清掃
- 運用ドキュメント: `docs/operations.md` （Claude Code セッション 5 で追加）
  - ストレージ選択 / メトリクス取得 / 監査整合性 / graceful shutdown / インシデント対応プレイブック
- Postgres統合テスト: `services/api/tests/test_postgres_integration.py` （Claude Code セッション 6 で追加）
  - `IVS_TEST_PG_DSN` 環境変数が設定されていれば実 DB に対して4ケース実行、未設定ならスキップ
- Postgres-integration CIジョブ: `.github/workflows/ci.yml` に追加（Claude Code セッション 6）
  - GitHub Actions の `services: postgres:16-alpine` を使用、`psycopg[binary]` を pip インストールしてテスト実行
- Grafanaダッシュボード: `docs/grafana/internet-voting-system.json` + README （Claude Code セッション 6 で追加）
  - `internet_voting_*` Prometheus metrics のみを参照するスタータダッシュボード
  - 候補者別カウントや個別票情報を絶対に表示しないことを README に明文化
- Postgresスキーマ適用ツール: `tools/init_postgres.py` （Claude Code セッション 6 で追加）
  - `--dsn` 必須、`--drop` で `DROP SCHEMA voting CASCADE` 後に再適用
  - 冪等。`postgresql_schema.sql` を読み込み autocommit モードで実行
- OpenAPI: `/metrics` に `text/plain` レスポンスと `?format=prometheus` query パラメータを追加（Claude Code セッション 6）
- OpenAPIプライバシーlint: `tools/lint_openapi_privacy.py` （Codex セッション4で追加）
  - OpenAPIのフィールド名・スキーマ名・パラメータ名に `mynumber` / `individual_number` / `個人番号` 等が混入したら失敗
  - 説明文に「禁止事項」として出る語は許容し、API契約上の名前だけを検査する
- CI: `.github/workflows/ci.yml` （Codex セッション4で追加）
  - Windows上でPython 3.12をセットアップ
  - Node.js 24をセットアップ
  - `tools/check_all.py` を実行（Codex セッション13）
- 手動スモーク負荷試験CI: `.github/workflows/loadtest.yml` （Codex セッション5で追加）
  - `workflow_dispatch` で `memory|sqlite`、voters、concurrency、receipt検証有無を指定して実行
  - Actions上でAPIサーバーを起動し、`tools/loadtest.py` を実行して終了時にサーバーを停止
  - 負荷試験前に `tools/smoke_check.py` を実行し、基本E2Eが通ってから並列負荷へ進むよう変更（Codex セッション11）

### 新エンドポイント

- `GET /elections/{id}/receipts/{receipt_hash}`
  - 受領証検証。Cast-as-Intended / Recorded-as-Cast を担保
  - サーバ側で再計算した receipt_hash と integrity_ok フラグを返す
  - voter_hash や accepted_candidate_id は応答に含めない
  - 未掲載の受領証は404ではなく `200 {found:false}` を返す。受領証探索をエラーテレメトリに載せないため、OpenAPIもこの挙動に合わせて補正済み
  - 64桁lowercase hexではない形式不正な受領証は `400 bad_request`
- `GET /audit-log/verify`
  - 監査ログのハッシュチェーンを最初から再計算
  - 改ざんがあれば `{valid:false, broken_at:<log_id>}` を返す

### エラー応答形式の統一

すべてのエラー応答が次の形式になった。Webクライアント側も対応済み。

```json
{ "error": { "code": "bad_request", "message": "..." } }
```

### 直近コミット

```text
5ec8667 Escape candidate display values
1186ef9 Add tally bars and candidate colors
e836cb5 Improve receipt verification display
caf3cca Add manual smoke load test workflow
aa30794 Improve bulletin board and audit log UI
f259a11 Add GitHub Actions CI
48a43bb Add OpenAPI privacy lint
a19c9a6 Add full-flow API load test tool
e978180 Add SQLite repository, receipt verification, audit-chain integrity
9667200 Add Claude Code handoff guide
```

セッション 2 コミット:

```text
e978180 Add SQLite repository, receipt verification, audit-chain integrity
```

セッション 3 コミット候補:

```text
Add full-flow API load test tool
```

セッション 4 コミット候補:

```text
Add OpenAPI privacy lint
Add GitHub Actions CI
Improve bulletin board and audit log UI
```

セッション 5 コミット候補:

```text
Add manual smoke load test workflow
```

セッション 6 コミット:

```text
1186ef9 Add tally bars and candidate colors
5ec8667 Escape candidate display values
```

セッション 7 コミット候補:

```text
Load test candidates from election metadata
```

セッション 8 コミット候補:

```text
Add HTTP API routing tests
```

## 実行方法

### API（メモリストレージ）

```powershell
Set-Location C:\Users\highd\Documents\Github\InternetVotingSystem\services\api
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m internet_voting_system.app --host 127.0.0.1 --port 8787 --storage memory
```

### API（SQLite永続化）

```powershell
Set-Location C:\Users\highd\Documents\Github\InternetVotingSystem\services\api
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m internet_voting_system.app --host 127.0.0.1 --port 8787 --storage sqlite --sqlite-path voting.sqlite3
```

### Webクライアント

```powershell
Set-Location C:\Users\highd\Documents\Github\InternetVotingSystem\client-web
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m http.server 8788 --bind 127.0.0.1
```

ブラウザ:

```text
http://127.0.0.1:8788
```

## テスト方法

```powershell
Set-Location C:\Users\highd\Documents\Github\InternetVotingSystem\services\api
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

期待値:

```text
Ran 27 tests
OK
```

## スモークチェック

APIを起動した状態で、リポジトリルートから実行する。

```powershell
Set-Location C:\Users\highd\Documents\Github\InternetVotingSystem
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools\smoke_check.py --base-url http://127.0.0.1:8787
```

期待値:

```json
{
  "status": "ok",
  "election_id": "demo-2026",
  "receipt_hash": "..."
}
```

## OpenAPIプライバシーlint

リポジトリルートから実行する。

```powershell
Set-Location C:\Users\highd\Documents\Github\InternetVotingSystem
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools\lint_openapi_privacy.py
```

期待値:

```text
OpenAPI privacy lint passed
```

## CI

`.github/workflows/ci.yml` で以下を自動実行する。

```powershell
Set-Location services\api
python -m unittest discover -s tests

Set-Location ..\..
python tools\lint_openapi_privacy.py
python -m py_compile tools\loadtest.py
python -m py_compile tools\lint_openapi_privacy.py
```

## 負荷試験

APIを起動した状態で、リポジトリルートから実行する。

```powershell
Set-Location C:\Users\highd\Documents\Github\InternetVotingSystem
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools\loadtest.py --base-url http://127.0.0.1:8787 --voters 100 --concurrency 10 --verify-receipts
```

出力はJSON形式。主な項目:

- `success` / `failed`
- `throughput_flows_per_second`
- `latency_ms.min` / `median` / `p95` / `max`
- `sample_errors`

SQLiteストレージでは書き込みが直列化されるため、並行度を上げるとロック待ちが増える。単一ホストの上限把握には使えるが、本番想定の負荷試験はPostgreSQL実装後に再実施すること。

## 同期方法

GitHub作業ツリーからGドライブ成果物保管先へ同期する。

```powershell
Copy-Item -LiteralPath `
  'C:\Users\highd\Documents\Github\InternetVotingSystem\.gitignore',`
  'C:\Users\highd\Documents\Github\InternetVotingSystem\README.md',`
  'C:\Users\highd\Documents\Github\InternetVotingSystem\DESIGN.md',`
  'C:\Users\highd\Documents\Github\InternetVotingSystem\build_xlsx.py',`
  'C:\Users\highd\Documents\Github\InternetVotingSystem\InternetVotingSystem_DesignDoc.xlsx' `
  -Destination 'G:\マイドライブ\claudecode\InternetVotingSystem' -Force

Copy-Item -LiteralPath `
  'C:\Users\highd\Documents\Github\InternetVotingSystem\services',`
  'C:\Users\highd\Documents\Github\InternetVotingSystem\client-web',`
  'C:\Users\highd\Documents\Github\InternetVotingSystem\docs',`
  'C:\Users\highd\Documents\Github\InternetVotingSystem\tools',`
  'C:\Users\highd\Documents\Github\InternetVotingSystem\.github' `
  -Destination 'G:\マイドライブ\claudecode\InternetVotingSystem' -Recurse -Force
```

同期後、`__pycache__` や `.pyc` が混入していないことを確認する。

## 設計上の注意

### デモ暗号と本番暗号の境界

現在の暗号実装は本番暗号ではなく、API境界と投票フローを確認するためのデモ実装である。

本番化時は `DemoCryptoSuite` を以下に置き換える。

- RFC 9474準拠のRSA Blind Signature
- ElGamal/ristretto255 による投票内容暗号化
- 候補者集合内であることのZKP
- DKGとShamir閾値復号
- JPKI/J-LIS照会と選挙人名簿APIの実接続
- WORMまたは改ざん耐性を持つ監査ログ基盤

### 上書き投票（補正済み・前セッション資料と同じ）

- `token_issued` は再発行禁止フラグではなく、過去に1回以上発行済みであることを示す監査フラグ。
- 同一トークンで再投票した場合は `revote_serial` 最大の票を採用する。
- 新トークン再発行を本格実装する場合、匿名投票ゾーンへ `voter_hash` を渡さず、認証ゾーン内で有効/失効トークンリストを作る。

### Repositoryバックエンドの切替

- `repository_base.py` の `Repository` プロトコルが正である。
- 新しいバックエンド（PostgreSQL等）を追加する場合は、このプロトコルを満たすクラスを書き、`app.main()` の分岐に追加する。
- サービス層（`service.py`）はバックエンド固有の API を呼ばないので、書き換え不要。

### マイナンバー（個人番号）非取得の機械的強制

`tests/test_audit_and_receipts.py::MyNumberAbsenceTest` が、主要レスポンスに
`mynumber` / `individual_number` / `my_number` / `個人番号` のいずれかが
含まれていれば失敗する。新エンドポイントを追加する場合は、このテストを
壊さないこと。

Codex セッション4で `tools/lint_openapi_privacy.py` を追加済み。OpenAPIの
フィールド名・スキーマ名・パラメータ名に同種の禁止語が入ると失敗する。
説明文で「禁止事項」として言及する文言は許容する設計。

## 次の推奨作業（優先順）

1. **PostgreSQLバックエンド**: `sqlite_repository.py` のスキーマを参考に、psycopg2/psycopgでPG実装を追加。`BEGIN IMMEDIATE` を `SELECT ... FOR UPDATE` に置き換える。
2. **FastAPI移行**: 標準ライブラリHTTPサーバーは並行性能と型付けに弱い。FastAPI＋Pydantic化し、OpenAPI を自動生成に切り替える。
3. **暗号ライブラリの実装差し替え**: `DemoCryptoSuite` のインターフェースを保ったまま、`blind-rsa-signatures` (Rust経由) ＋ `ristretto255` ベースのElGamal実装に置換。Pythonからは PyO3 バインディング or subprocess で呼ぶ。
4. **Webクライアントの強化**:
   - 集計プレビューから受領証検証や公開掲示板への導線を追加
5. **CI拡充**: 最小CIと手動スモーク負荷試験workflowは追加済み。次はGitHub Actionsの実行結果を見て、必要なら `loadtest.yml` の起動待ちやタイムアウトを調整する。
6. **負荷試験結果の拡充**: `tools/loadtest.py` と `docs/performance.md` は追加済み。より大きい `--voters` と `--concurrency` で、ロック待ち・失敗率・p95を追記する。
7. ~~**コンテナ化**: 各バックエンドを Dockerfile 化。~~ → Claude Code セッション 3 で実装、セッション 4 で CI 化済。
8. ~~**APIシャットダウン用 signal handler**~~ → Claude Code セッション 4 で実装済（`install_graceful_shutdown()`）。
9. ~~**PostgreSQLバックエンドの実装本体**~~ → セッション 5 で実装、セッション 6 で `services: postgres` 統合テスト＋CIジョブまで完了。
10. **本番暗号への置き換え**: `DemoCryptoSuite` インターフェースを保ったまま、`blind-rsa-signatures` / ristretto255 ベース実装に差し替える。
11. ~~**メトリクスのPrometheus化**~~ → セッション 5 で対応、セッション 6 で Grafana ダッシュボード追加済。
12. ~~**Docker compose プロファイルでの smoke 検証**~~ → セッション 5 で `compose-smoke` CIジョブ追加済。
13. ~~**Postgres専用テスト**~~ → セッション 6 で `test_postgres_integration.py` 追加済。
14. ~~**OpenAPI に /metrics の Prometheus レスポンスを追記**~~ → セッション 6 で追記済。
15. **クライアント側 JPKI 実接続**: Web版は公的個人認証JPKIブラウザ拡張、モバイル版はNFC SDK を組み込み、`certificate_serial` 直接入力フォームを置き換える。
16. **負荷試験のPostgres版**: `tools/loadtest.py` を `--storage postgres` で起動した API に対して実行し、結果を `docs/performance.md` に追記。FOR UPDATE による直列化の影響を測定。
17. **WAF/CDNのIaCサンプル**: `docs/infrastructure/` を作成し、Cloudflare or AWS のWAFルール（レート制限、CAPTCHA、Botblocker）と CDN 配信構成を Terraform で例示。

## 既知の制約

- `--storage sqlite` でホストを跨いだ複数プロセス運用は安全ではない（WALだが書き込みは直列）。本番では PostgreSQL 必須。
- `verify_audit_chain` は現状すべてのログを読み出して再計算する。エントリ数が1000万を超える場合はチェックポイント方式に変更する必要がある。
- Webクライアントはまだ JPKI のローカル署名は行わず、`certificate_serial` を入力する簡易フローのみ。本番のWeb版は JPKI ブラウザ拡張、モバイル版は NFC SDK を組み込む必要がある。
