# インターネット投票システム v0.2.0

マイナンバーカード活用インターネット投票システムの**実装プロトタイプ**です。
JPKI／ブラインド署名／ZKP／ミックスネット／閾値復号といった本番実装の境界をモジュール分離し、
現段階では標準ライブラリだけで動くデモ用暗号アダプタ（`DemoCryptoSuite`）で各暗号要素を独立確認できます。

> ⚠️ **本番投票には絶対に使用しないでください。** 設計検証のためのプロトタイプです。

## 主な機能

- 投票フロー API（JPKI 本人確認 → ブラインド署名投票券発行 → 暗号化票＋ZKP 生成 → 投票送信）
- 公開掲示板（bulletin board）と受領証検証（Cast-as-Intended / Recorded-as-Cast）
- 集計プレビュー（tally）
- 監査ログとハッシュチェーン整合性検証（サーバを信用しないローカル再計算にも対応）
- ストレージ切替：メモリ（揮発）／ SQLite（単一ホスト永続）／ PostgreSQL
- 分散レート制限（Redis 対応）、Prometheus メトリクス、グレースフルシャットダウン
- ブラウザ用簡易投票クライアント（`client-web/`）
- 監査者向け Python SDK（`ivs_client`）、TypeScript/ESM SDK
- 周辺資産：OpenAPI 定義、Docker / docker-compose、Kubernetes Helm chart、WAF/CDN の IaC サンプル、Grafana ダッシュボード

## 動作環境

- Python 3.10 以降（API は標準ライブラリのみで動作、`pip install` 不要）
- Docker / docker-compose（任意・コンテナ実行する場合）
- OS 非依存（Windows / macOS / Linux）。Node.js は TypeScript SDK 利用時のみ

## このリリースの変更点（v0.2.0）

### Added
- セキュリティ中核モジュール `crypto.py`（`DemoCryptoSuite`）の専用単体テスト（19 ケース）を追加。
  トークン署名/検証、改ざん・鍵不一致・選挙不一致・不正フォーマットの拒否、投票暗号の往復、
  ZK 証明の受理/候補集合外拒否/改ざん拒否などの不変条件を直接検証（API ユニットテスト 80→99）。
- README に「これは何？（30秒で）」「想定ユースケース・価格帯」セクションを追加。
- `SECURITY.md` を追加（脆弱性報告フロー）。
- 商用利用・カスタマイズ依頼の連絡先を README 末尾に明記。

詳細は [`CHANGELOG.md`](../CHANGELOG.md) を参照してください。

## ライセンス / 連絡先

- MIT License（同梱の [`LICENSE`](../LICENSE) を参照）
- https://github.com/highdefinitionaudiodriver/InternetVotingSystem
- highdefinitionaudiodriver@gmail.com
