# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- セキュリティ中核モジュール `crypto.py`（DemoCryptoSuite）の専用単体テスト `services/api/tests/test_crypto.py`（19ケース）を追加。これまでサービス層経由でしか検証されていなかったトークン署名/検証、改ざん・鍵不一致・選挙不一致・不正フォーマットの拒否、投票暗号の往復と選挙不一致拒否、ZK 証明の受理/候補集合外拒否/改ざん拒否、b64url 往復・canonical_json のキー順非依存などの不変条件を直接検証（API ユニットテスト 80→99）
- README に「これは何？（30秒で）」「想定ユースケース・価格帯」セクションを追加
- SECURITY.md を追加（脆弱性報告フロー）
- 商用利用・カスタマイズ依頼の連絡先を README 末尾に明記

## [0.1.0]

### Added
- 初版リリース
