# Claude Code / Codex 引き継ぎ資料

最終更新: 2026-05-18 (Codex セッション 18 終了時)

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
  - `test_lifecycle_ratelimit_pagination.py` （Claude Code セッション 7 で追加、9件）
  - `test_backup_sqlite_tool.py` （Claude Code セッション 7 で追加、2件）
  - `test_helm_chart_lint.py` （Codex セッション14で追加、3件）
  - `test_lifecycle_ratelimit_pagination.py` に環境変数rate limit設定テスト3件を追加（Codex セッション15）
  - `test_infrastructure_docs_lint.py` （Codex セッション16で追加、3件）
  - `test_audit_checkpoints_and_redis.py` （Claude Code セッション 8 で追加、11件）
  - `test_redis_integration.py` （Codex セッション17で追加、2件。`IVS_TEST_REDIS_URL` 設定時のみ実行）
  - `test_audit_checkpoints_endpoint.py` （Claude Code セッション 9 で追加、7件）
  - APIテスト計80件（DSN/Redis未設定では postgres 4件 + redis 2件スキップ、残り74件すべてパス）
  - **SDKテスト**: `clients/python/tests/test_voting_client.py` 7件（Claude Code セッション 10 で追加）
  - **TypeScript SDKテスト**: `clients/typescript/tests/client.test.mjs` 5件（Codex セッション 18 で追加）
  - 合計92件（CI実行時は全件、ローカルでは PG/Redis 環境変数の有無で増減）
- スモークチェック: `tools/smoke_check.py` （Codex セッション10で追加）
  - 起動済みAPIに対して health、投票フロー、受領証検証、監査ログ整合性を単発確認
  - CIの構文チェック対象にも追加済み
- ローカル統合チェック: `tools/check_all.py` （Codex セッション13で追加）
  - APIユニットテスト、OpenAPIプライバシーlint、Helm chart静的lint、Web JS構文、standalone tools構文を一括実行
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
- レート制限: `rate_limit.RateLimiter`（Claude Code セッション 7 で追加）
  - IP単位のtoken bucket。write/read別の容量・refill。デフォルトは write 30 burst+5/s、read 120 burst+30/s
  - `app.py` で全 GET（health/metrics除く）/全 POST に適用
  - `X-Forwarded-For` を honor（CDN/WAFがクライアント側値を必ず上書きする前提）
  - `429 rate_limited` を返却、エラー envelope `{error:{code,message}}`
  - Codex セッション15で `IVS_RATE_LIMIT_*` 環境変数による有効/無効化・容量/補充量設定を追加
  - Helm chartの `values.yaml` `rateLimit` セクションからAPI Deployment環境変数へ反映
  - クラス属性 `VotingRequestHandler.rate_limiter = None` で無効化可能（テスト用）
- 選挙クローズエンドポイント: `POST /elections/{id}/close` （Claude Code セッション 7 で追加）
  - `Election.status` を `closed` に遷移、以後 authenticate / issue-token / submit-ballot は `not open` エラー
  - 監査ログに `election_closed` イベントを記録
  - Repository プロトコルに `set_election_status()` を追加し、memory/SQLite/Postgres 全実装に展開
- 監査ログのページング: `GET /audit-log?after=<log_id>&limit=<n>` （Claude Code セッション 7 で追加）
  - `limit` 1〜1000（デフォルト200）、`next_after` と `has_more` を返却
  - 1000万エントリ規模でも leveraged-cost を抑える設計
- SQLiteオンライン・バックアップツール: `tools/backup_sqlite.py` （Claude Code セッション 7 で追加）
  - `Connection.backup()` API を用い、稼働中DBに対し書き込みを止めずに一貫スナップショット取得
  - 取得後 `PRAGMA integrity_check` で検証、失敗時 exit code 2
- Helm chart: `deploy/helm/internet-voting-system/` （Claude Code セッション 7 で追加）
  - API/Web Deployment + Service、SQLite用PVC、Postgres用Secret、PodDisruptionBudget
  - `storage.backend` 切替で memory/sqlite/postgres を選択可能
- Helm chart静的lint: `tools/lint_helm_chart.py` （Codex セッション14で追加）
  - Helm CLIなしでChart.yaml/values.yaml/主要templateの存在、必須スニペット、`{{`/`}}` の対応を検査
  - `tools/check_all.py` とCIの通常チェック経由で実行される
  - 本物の `helm lint` / `helm template` を置き換えるものではないため、Helm導入後のCI拡張は引き続き推奨
  - SQLite時は強制的に replicaCount=1（PVC競合回避）
  - Postgres時に dsn 未指定なら `helm template` が `fail` で停止
- Infrastructure docs: `docs/infrastructure/` （Codex セッション16で追加）
  - `aws-waf-cloudfront/` にAWS WAFv2 + CloudFront向けTerraformサンプルを追加
  - IP reputation / anonymous IP / common / known bad inputs / API path rate limit を定義
  - WAFログのsampled requestを無効にし、票本文・候補者別集計・受領証などをエッジログへ積極的に出さない方針をREADMEに明記
- RateLimiterプロトコル化 + Redis分散実装: `services/api/internet_voting_system/rate_limit.py` （Claude Code セッション 8）
  - `RateLimiterProtocol` を新設、既存 `RateLimiter` を in-memory 実装として温存（後方互換）
  - `RedisRateLimiter`: 単一の Lua スクリプトで HMGET → 補充 → 判定 → HMSET → EXPIRE を atomic に実行
  - `redis` パッケージは遅延 import、未インストールでも build_rate_limiter_from_env 経路を踏むまでエラー出ない
  - `build_rate_limiter_from_env` を拡張: `IVS_RATE_LIMIT_BACKEND=memory|redis`、`IVS_RATE_LIMIT_REDIS_URL` を解釈
- Redis統合テスト: `services/api/tests/test_redis_integration.py` + `docker-compose.test.yml` + CI `redis-integration` ジョブ（Codex セッション17）
  - `IVS_TEST_REDIS_URL` 未設定なら通常テストではスキップ
  - GitHub Actionsでは `redis:7-alpine` サービスを起動し、`redis>=5` をインストールして実Redisに対して共有bucket/TTLを検証
- 監査チェーン検証チェックポイント対応: `verify_audit_chain(from_log_id, expected_prev_hash)` （Claude Code セッション 8）
  - `repository_base._verify_chain` 共通ヘルパに集約、3バックエンドで挙動が完全に一致
  - `GET /audit-log/verify?from=<log_id>&prev_hash=<head_hash>` で前回確認した chunk から再開可能
  - 既存の引数なし呼び出しはこれまで通り、レスポンスに `verified_from` フィールドを追加
- Python SDK: `clients/python/ivs_client/` （Claude Code セッション 10 で追加）
  - stdlib のみ。`VotingClient.health/list_elections/...` で OpenAPI と1:1の薄いラッパ
  - `iter_audit_log()` ジェネレータが `?after=&limit=` を自動ページング
  - `verify_audit_chain_locally()` でサーバ側 `/audit-log/verify` を信用せずクライアント側でハッシュチェーンを再計算
  - エラー応答 `{error:{code,message}}` を `ApiError` 例外に変換
  - `pyproject.toml` で `pip install -e clients/python` 可能（PyPI公開はしない）
  - `tests/test_voting_client.py` 7件。`ApiError` 例外パス、ローカル replay vs サーバ verify の一致、SDK 公開API に `mynumber` 等の禁止パラメータが含まれないことを保証
  - `tools/check_all.py` 経由で API テストとは別ステップで実行される
- TypeScript SDK: `clients/typescript/` （Codex セッション 18 で追加）
  - 依存なし、fetchベースの async ESM クライアント。ブラウザ/Node 18+想定
  - Python SDKと同じくAPI routeに対応する薄いラッパ、`iterAuditLog()` と `verifyAuditChainLocally()` を提供
  - `src/index.js` は実行用ESM、`src/index.ts` は型付きソース/宣言面。npm公開はせずソース配布
  - `clients/typescript/tests/client.test.mjs` は Node 標準 `node:test` で routing、ApiError、ページング、ローカル監査チェーン再計算、禁止パラメータ非露出を検証
  - `tools/check_all.py` に `node --check clients/typescript/src/index.js` と `node --test clients/typescript/tests/client.test.mjs` を追加済み
- OpenAPI `$ref` 整合性チェッカ: `tools/validate_openapi_refs.py` （Claude Code セッション 10 で追加）
  - 全 `$ref: "#/components/.../X"` が定義済コンポーネントを指すか、孤児コンポーネントが残っていないかを静的検査
  - stdlib のみで実装（yaml パーサ非依存）
- Infrastructure-validate CIジョブ: `.github/workflows/ci.yml` `infrastructure-validate` ジョブ（Claude Code セッション 10）
  - `hashicorp/setup-terraform@v3` で Terraform 1.7.5 をインストール
  - `terraform fmt -check -recursive` → `terraform init -backend=false` → `terraform validate` を `docs/infrastructure/aws-waf-cloudfront/` で実行
- 監査チェックポイントAPI: `GET /audit-log/checkpoints?interval=<n>&limit=<m>` （Claude Code セッション 9 で追加）
  - N件毎の `(log_id, log_hash)` を newest-first で返却。tail エントリは常に含める
  - クライアントは最新チェックポイントを `/audit-log/verify?from=&prev_hash=` に渡して差分検証
  - `interval >= 1`、`1 <= limit <= 100` を検証、それ以外は `400 bad_request`
  - 候補別票数や voter_hash は応答に含まれないことを `test_checkpoint_does_not_leak_identity` が保証
- WAF/CDN拡張: `docs/infrastructure/aws-waf-cloudfront/cloudfront.tf` （Claude Code セッション 9 で追加）
  - `var.create_distribution = true` で opt-in 化されたCloudFront Distribution
  - 動的パスは `min_ttl=default_ttl=max_ttl=0` でエッジキャッシュ無効（受領証検証や監査ログを汚さない）
  - WAF → Kinesis Firehose → S3 (Object Lock COMPLIANCE) でWAFログをWORM保管
  - `aws_wafv2_web_acl_logging_configuration.redacted_fields` で `authorization` / `cookie` / `certificate_serial` をWAFログから除外
  - `tools/lint_infrastructure_docs.py` を拡張し、Object Lock / Firehose / redact指定の存在を静的検査
- helm-chart-testing CIジョブ: `.github/workflows/ci.yml` `helm-chart-testing` ジョブ（Claude Code セッション 8）
  - 本物の `helm lint` + `helm template` を memory/sqlite/postgres 3プロファイルで実行
  - `kubeconform -strict` でレンダ済みマニフェストを Kubernetes スキーマ検証
- Infrastructure docs lint: `tools/lint_infrastructure_docs.py` （Codex セッション16で追加）
  - WAFサンプルの必須ファイル、主要AWS管理ルール、IPベースrate limit、`sampled_requests_enabled = false` を検査
  - `tools/check_all.py` とCIの通常チェック経由で実行される
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
  'C:\Users\highd\Documents\Github\InternetVotingSystem\clients',`
  'C:\Users\highd\Documents\Github\InternetVotingSystem\docs',`
  'C:\Users\highd\Documents\Github\InternetVotingSystem\tools',`
  'C:\Users\highd\Documents\Github\InternetVotingSystem\.github',`
  'C:\Users\highd\Documents\Github\InternetVotingSystem\deploy',`
  'C:\Users\highd\Documents\Github\InternetVotingSystem\Dockerfile',`
  'C:\Users\highd\Documents\Github\InternetVotingSystem\Dockerfile.web',`
  'C:\Users\highd\Documents\Github\InternetVotingSystem\docker-compose.yml',`
  'C:\Users\highd\Documents\Github\InternetVotingSystem\docker-compose.test.yml' `
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
17. ~~**WAF/CDNのIaCサンプル**: `docs/infrastructure/` を作成し、Cloudflare or AWS のWAFルール（レート制限、CAPTCHA、Botblocker）と CDN 配信構成を Terraform で例示。~~ → Codex セッション16でAWS WAF + CloudFrontのTerraformサンプルと静的lintを追加済み。CloudFront Distribution本体やWAFログ配送は未実装。
18. ~~**Helmチャートの helm lint / helm template CI**~~ → Claude Code セッション 8 で `helm-chart-testing` ジョブ追加（helm + kubeconform）。
19. **本番暗号への置き換え**: `DemoCryptoSuite` インターフェースを保ったまま、`blind-rsa-signatures` / ristretto255 ベース実装に差し替える（積み残し最重要）。
20. ~~**レート制限の分散化**~~ → Claude Code セッション 8 で `RedisRateLimiter` 実装、Codex セッション17で実Redis統合テストCIと `docker-compose.test.yml` まで追加済み。
21. ~~**監査チェーンチェックポイントAPI**~~ → Claude Code セッション 9 で `/audit-log/checkpoints` を追加。次は `audit_log` に専用 `checkpoint` 列を増やし、N件毎の hash を永続化（現在はオンザフライ計算）。
22. ~~**CloudFront Distribution 本体 + WAFログ配送**~~ → Claude Code セッション 9 で `cloudfront.tf` を opt-in 追加（Distribution + Firehose + S3 Object Lock + redacted_fields）。次は `terraform validate` / `terraform plan` を CI で回す `infrastructure-validate` ジョブを追加。
23. ~~**クライアントSDK**~~ → Claude Code セッション 10 で Python SDK `clients/python/ivs_client/`、Codex セッション18で TypeScript/ESM SDK `clients/typescript/` を追加。次は Web クライアントからSDKを直接 import する形に寄せる。
24. **本番暗号への置き換え**（積み残し最重要・このセッションでも未着手）
25. **`audit_log.checkpoint` カラム永続化**: 現在 `/audit-log/checkpoints` はオンザフライ計算。N件毎の checkpoint を `audit_log` テーブルに永続化すれば、API 再起動直後でも即応答可能。schema migration を追加して 3 バックエンドへ展開する必要がある。
26. **CIマトリクス整理**: 現状 7 ジョブ（test / docker-build / postgres-integration / redis-integration / helm-chart-testing / compose-smoke / infrastructure-validate）。並列実行コストが見えてきたら `needs:` を整理して critical path を短縮する。

## 既知の制約

- `--storage sqlite` でホストを跨いだ複数プロセス運用は安全ではない（WALだが書き込みは直列）。本番では PostgreSQL 必須。
- `verify_audit_chain` は現状すべてのログを読み出して再計算する。エントリ数が1000万を超える場合はチェックポイント方式に変更する必要がある。
- Webクライアントはまだ JPKI のローカル署名は行わず、`certificate_serial` を入力する簡易フローのみ。本番のWeb版は JPKI ブラウザ拡張、モバイル版は NFC SDK を組み込む必要がある。
