# Internet Voting System

マイナンバーカード活用インターネット投票システムの実装プロトタイプです。

このリポジトリは、設計書 `DESIGN.md` の考え方を崩さず、まずローカルで検証できる最小構成を提供します。JPKI、ブラインド署名、ZKP、ミックスネット、閾値復号は本番実装の境界を意識したモジュールに分け、現段階では標準ライブラリだけで動くデモ用アダプタを使っています。

## 構成

- `services/api/internet_voting_system/` - 投票APIサーバー
- `services/api/tests/` - APIとドメインロジックのテスト
- `client-web/` - ブラウザで動く簡易投票クライアント
- `docs/api/openapi.yaml` - API定義
- `DESIGN.md` - システム設計書
- `InternetVotingSystem_DesignDoc.xlsx` - Excel版設計書

## 実行

作業ディレクトリは `services/api` にしてください。

メモリストレージ（揮発・デモ用）:

```powershell
Set-Location services\api
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m internet_voting_system.app --host 127.0.0.1 --port 8787 --storage memory
```

SQLiteストレージ（永続化・単一ホスト用）:

```powershell
Set-Location services\api
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m internet_voting_system.app --host 127.0.0.1 --port 8787 --storage sqlite --sqlite-path voting.sqlite3
```

クライアントは `client-web/index.html` をブラウザで開き、API URLに `http://127.0.0.1:8787` を指定します。
受領証検証パネルと監査ログ整合性チェックパネルが追加されています。

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
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

## OpenAPIプライバシーlint

OpenAPIのフィールド名・スキーマ名・パラメータ名に、マイナンバー取得を示す名前が混入していないか確認できます。

```powershell
Set-Location C:\Users\highd\Documents\Github\InternetVotingSystem
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools\lint_openapi_privacy.py
```

## スモークチェック

APIサーバーを起動した状態で、単一の投票フロー、受領証検証、監査ログ整合性をまとめて確認できます。

```powershell
Set-Location C:\Users\highd\Documents\Github\InternetVotingSystem
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools\smoke_check.py --base-url http://127.0.0.1:8787
```

## 負荷試験

APIサーバーを起動した状態で、別ターミナルからフルフローの簡易負荷試験を実行できます。

```powershell
Set-Location C:\Users\highd\Documents\Github\InternetVotingSystem
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' tools\loadtest.py --voters 100 --concurrency 10 --verify-receipts
```

標準出力に成功件数、失敗件数、スループット、レイテンシをJSONで出力します。SQLiteストレージでは書き込みが直列化されるため、並行度を上げるとロック待ちが増えます。
候補者IDは `GET /elections/{id}` から取得するため、`demo-2026` 以外の選挙にも利用できます。

## 実装上の注意

このプロトタイプは制度・暗号方式の実証用です。本番利用には、設計書の通り RFC 9474 準拠ブラインド署名、ElGamal/ristretto255、Chaum-Pedersen系ZKP、DKG、Shamir閾値復号、JPKI/選挙人名簿APIの実接続、WORM監査基盤が必要です。
