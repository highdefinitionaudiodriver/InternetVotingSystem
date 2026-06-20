# Internet Voting System

マイナンバーカード活用インターネット投票システムの実装プロトタイプです。

このリポジトリは、設計書 `DESIGN.md` の考え方を崩さず、まずローカルで検証できる最小構成を提供します。JPKI、ブラインド署名、ZKP、ミックスネット、閾値復号は本番実装の境界を意識したモジュールに分け、現段階では標準ライブラリだけで動くデモ用アダプタを使っています。

---

## 🎯 これは何？（30秒で）

- **誰のため**：選挙インフラの研究者・自治体DX担当・電子投票プロトタイプを評価したい議員／市民団体
- **何が解決される**：「マイナンバーカードで本人確認しつつ匿名性を担保する電子投票」の **設計・実装パターンの参考実装**。本番実装の境界（JPKI／ブラインド署名／ZKP／ミックスネット／閾値復号）をモジュール分離して可視化
- **なぜ既存ツールではダメか**：商用電子投票プラットフォームは中身がブラックボックス。本ツールは **OSS で各暗号要素を独立確認可能**で、議論・査読の土台になる
- **使う条件**：Python 3.10+ / Node.js（クライアント）／ローカル検証用

> ⚠️ **本番投票には絶対に使用しないでください**。これは設計検証のためのプロトタイプです。

## 💰 想定ユースケース・価格帯

| 用途 | 形態 |
|---|---|
| 設計参考・学術研究・自治体PoC評価 | 無料（MIT） |
| 議員・自治体向けデモ実演、設計レビュー受託 | 応相談 |
| 本番実装に向けた暗号モジュール置換・監査 | 個別見積もり |

---

## 構成

- `services/api/internet_voting_system/` - 投票APIサーバー
- `services/api/tests/` - APIとドメインロジックのテスト
- `client-web/` - ブラウザで動く簡易投票クライアント
- `clients/python/` - Python SDK
- `clients/typescript/` - TypeScript/ESM SDK
- `docs/api/openapi.yaml` - API定義
- `docs/infrastructure/` - WAF/CDNなど周辺インフラのIaCサンプル
- `clients/python/` - 監査者・観察者向け Python SDK（stdlibのみ、`ivs_client`）
- `deploy/helm/` - Kubernetes Helm chart
- `DESIGN.md` - システム設計書
- `InternetVotingSystem_DesignDoc.xlsx` - Excel版設計書

## 実行

作業ディレクトリは `services/api` にしてください。

メモリストレージ（揮発・デモ用）:

```powershell
Set-Location services\api
python -m internet_voting_system.app --host 127.0.0.1 --port 8787 --storage memory
```

SQLiteストレージ（永続化・単一ホスト用）:

```powershell
Set-Location services\api
python -m internet_voting_system.app --host 127.0.0.1 --port 8787 --storage sqlite --sqlite-path voting.sqlite3
```

クライアントは `client-web/index.html` をブラウザで開き、API URLに `http://127.0.0.1:8787` を指定します。
受領証検証パネルと監査ログ整合性チェックパネルが追加されています。

## Docker での起動

リポジトリルートに `Dockerfile`、`Dockerfile.web`、`docker-compose.yml` を用意してあります。
標準ライブラリのみで動くため、`pip install` も不要です。

メモリストレージ（揮発）:

```powershell
docker compose --profile memory up --build
```

SQLiteストレージ（名前付きボリュームに永続化）:

```powershell
docker compose --profile sqlite up --build
```

いずれもAPIが `http://localhost:8787`、Webクライアントが `http://localhost:8788` で立ち上がります。
ボリューム `vote-data` を削除しない限り、SQLiteプロファイルでは投票記録と監査ログがコンテナ再作成後も保持されます。

## 主なエンドポイント

- `POST /elections/{id}/authenticate` - JPKI証明書による本人確認
- `POST /elections/{id}/issue-token` - ブラインド署名投票券発行
- `POST /elections/{id}/prepare-vote` - 暗号化票とZKP生成
- `POST /elections/{id}/ballots` - 暗号化票送信
- `GET  /elections/{id}/bulletin-board` - 公開掲示板
- `GET  /elections/{id}/receipts/{hash}` - 受領証検証（Cast-as-Intended/Recorded-as-Cast）
- `GET  /elections/{id}/tally` - 集計プレビュー
- `GET  /audit-log` - 監査ログ
- `GET  /audit-log/verify` - 監査ログ・ハッシュチェーン整合性検証

エラー応答は `{ "error": { "code": "...", "message": "..." } }` 形式で統一されています。

## テスト

```powershell
Set-Location services\api
python -m unittest discover -s tests
```

CI相当のチェックをまとめて実行する場合:

```powershell
# （リポジトリのルートディレクトリで実行してください）
python tools\check_all.py
```

## SDK

Python SDK:

```powershell
Set-Location clients\python
python -m unittest discover -s tests
```

TypeScript/ESM SDK:

```powershell
Set-Location clients\typescript
node --test tests\client.test.mjs
```

## OpenAPIプライバシーlint

OpenAPIのフィールド名・スキーマ名・パラメータ名に、マイナンバー取得を示す名前が混入していないか確認できます。

```powershell
# （リポジトリのルートディレクトリで実行してください）
python tools\lint_openapi_privacy.py
```

## Infrastructure docs lint

`docs/infrastructure/` のWAF/CDNサンプルに、必須ファイルやプライバシー保護上の設定が残っているか確認できます。

```powershell
# （リポジトリのルートディレクトリで実行してください）
python tools\lint_infrastructure_docs.py
```

## スモークチェック

APIサーバーを起動した状態で、単一の投票フロー、受領証検証、監査ログ整合性をまとめて確認できます。

```powershell
# （リポジトリのルートディレクトリで実行してください）
python tools\smoke_check.py --base-url http://127.0.0.1:8787
```

## 負荷試験

APIサーバーを起動した状態で、別ターミナルからフルフローの簡易負荷試験を実行できます。

```powershell
# （リポジトリのルートディレクトリで実行してください）
python tools\loadtest.py --voters 100 --concurrency 10 --verify-receipts
```

標準出力に成功件数、失敗件数、スループット、レイテンシをJSONで出力します。SQLiteストレージでは書き込みが直列化されるため、並行度を上げるとロック待ちが増えます。
候補者IDは `GET /elections/{id}` から取得するため、`demo-2026` 以外の選挙にも利用できます。

## Python SDK（監査者向け）

`clients/python/` 配下に stdlib のみで動く薄い SDK があります。受領証検証、監査ログのページング、ハッシュチェーンのローカル再計算（サーバ側 `verify` を信用しない検証）を提供します。

```powershell
Set-Location clients\python
pip install -e .
python -c "from ivs_client import VotingClient; print(VotingClient('http://127.0.0.1:8787').health())"
```

```python
from ivs_client import VotingClient
client = VotingClient("http://127.0.0.1:8787")
ckpts = client.audit_checkpoints(interval=1000)
latest = ckpts["checkpoints"][0]
result = client.verify_audit_chain(from_log_id=latest["log_id"], prev_hash=latest["log_hash"])
assert result["valid"]
# あるいは全エントリをローカルで再計算（サーバの verify エンドポイントを信用しない）
assert client.verify_audit_chain_locally()["valid"]
```

## Redis統合テスト

分散レート制限の実Redisテストは通常の `tools\check_all.py` ではスキップされます。ローカルで確認する場合:

```powershell
docker compose -f docker-compose.test.yml up -d redis
Set-Location services\api
$env:IVS_TEST_REDIS_URL = 'redis://127.0.0.1:6379/0'
pip install 'redis>=5'
python -m unittest tests.test_redis_integration -v
Set-Location ..\..
docker compose -f docker-compose.test.yml down --volumes
```

## 実装上の注意

このプロトタイプは制度・暗号方式の実証用です。本番利用には、設計書の通り RFC 9474 準拠ブラインド署名、ElGamal/ristretto255、Chaum-Pedersen系ZKP、DKG、Shamir閾値復号、JPKI/選挙人名簿APIの実接続、WORM監査基盤が必要です。

---

## 🤝 商用利用・カスタマイズ依頼

- 個人・社内利用は無料（MIT ライセンス）
- 法人・自治体・SI 向け導入支援、カスタマイズ、診断レポート受託は応相談
- 連絡先：highdefinitionaudiodriver@gmail.com

<!-- CODEX-CURRENT-STATUS:START -->
## 現状サマリ (2026-06-21)

- 対象: Internet Voting System
- 作業ブランチ: main / リリース版数: v0.2.0
- API ユニットテスト 99 件パス（Redis / Postgres 実接続テストは環境変数指定時のみ実行）。
- Dockerfile / docker-compose.yml を同梱し、コンテナ実行・ローカル統合検証に展開可能。
- docs ディレクトリ配下に設計・運用・補足資料を配置。
- LICENSE（MIT）を同梱し、版数を 0.2.0 系へ統一済み。
- 主要な確認コマンド: README 記載のセットアップ・検証コマンド
- 暗号コアは `DemoCryptoSuite`（デモ用アダプタ）。本番投票には設計書記載の暗号方式・JPKI 実接続・WORM 監査基盤への置換が必須。
<!-- CODEX-CURRENT-STATUS:END -->

