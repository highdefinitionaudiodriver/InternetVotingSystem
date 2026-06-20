# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- ルートに `LICENSE`（MIT）を同梱（README/RELEASE_NOTES の MIT 表記と整合）。
- `SqliteRepository` に `close()` とコンテキストマネージャ（`__enter__`/`__exit__`）を追加。

### Changed
- 版数を 0.2.0 系へ統一（`internet_voting_system.__version__`、`SECURITY.md` の Supported Versions）。
- README のセットアップ手順からマシン固有の Python 絶対パス・作業ディレクトリ絶対パスを除去し、`python` と相対パスへ置換。
- `release_kit/RELEASE_NOTES.md` をプレースホルダから実内容（機能一覧・動作環境・変更点）へ更新。

### Fixed
- SQLite 接続のクローズ漏れに起因するテスト時 `ResourceWarning`（unclosed database）を解消。

## [0.2.0] - 2026-06-04

### Added
- セキュリティ中核モジュール `crypto.py`（DemoCryptoSuite）の専用単体テスト `services/api/tests/test_crypto.py`（19ケース）を追加。これまでサービス層経由でしか検証されていなかったトークン署名/検証、改ざん・鍵不一致・選挙不一致・不正フォーマットの拒否、投票暗号の往復と選挙不一致拒否、ZK 証明の受理/候補集合外拒否/改ざん拒否、b64url 往復・canonical_json のキー順非依存などの不変条件を直接検証（API ユニットテスト 80→99）
- README に「これは何？（30秒で）」「想定ユースケース・価格帯」セクションを追加
- SECURITY.md を追加（脆弱性報告フロー）
- 商用利用・カスタマイズ依頼の連絡先を README 末尾に明記

## [0.1.0]

### Added
- 初版リリース
