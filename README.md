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

```powershell
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m internet_voting_system.app --host 127.0.0.1 --port 8787
```

作業ディレクトリは `services/api` にしてください。

```powershell
Set-Location services\api
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m internet_voting_system.app --host 127.0.0.1 --port 8787
```

クライアントは `client-web/index.html` をブラウザで開き、API URLに `http://127.0.0.1:8787` を指定します。

## テスト

```powershell
Set-Location services\api
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

## 実装上の注意

このプロトタイプは制度・暗号方式の実証用です。本番利用には、設計書の通り RFC 9474 準拠ブラインド署名、ElGamal/ristretto255、Chaum-Pedersen系ZKP、DKG、Shamir閾値復号、JPKI/選挙人名簿APIの実接続、WORM監査基盤が必要です。
