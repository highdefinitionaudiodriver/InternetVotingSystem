---
title: "インターネット投票システム を作った"
tags: ["電子投票", "python", "個人開発", "OSS"]
private: false
---

> Qiita 投稿用の記事です。先頭の frontmatter（title / tags / private）は投稿スクリプトがメタ情報として読み取り、本文には含めません。

## TL;DR

マイナンバーカード活用インターネット投票システムの実装プロトタイプです。

- リポジトリ: https://github.com/highdefinitionaudiodriver/InternetVotingSystem
- ライセンス: MIT

## 作った背景・課題

- **誰のため**：選挙インフラの研究者・自治体DX担当・電子投票プロトタイプを評価したい議員／市民団体
- **何が解決される**：「マイナンバーカードで本人確認しつつ匿名性を担保する電子投票」の **設計・実装パターンの参考実装**。本番実装の境界（JPKI／ブラインド署名／ZKP／ミックスネット／閾値復号）をモジュール分離して可視化
- **なぜ既存ツールではダメか**：商用電子投票プラットフォームは中身がブラックボックス。本ツールは **OSS で各暗号要素を独立確認可能**で、議論・査読の土台になる
- **使う条件**：Python 3.10+ / Node.js（クライアント）／ローカル検証用

> ⚠️ **本番投票には絶対に使用しないでください**。これは設計検証のためのプロトタイプです。

## 使い方

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

## おわりに

- 個人・社内利用は無料（MIT ライセンス）
- 法人・自治体・SI 向け導入支援、カスタマイズ、診断レポート受託は応相談
- 連絡先：highdefinitionaudiodriver@gmail.com

個人・社内利用は MIT ライセンスで無料です。フィードバックは Issues / Star をいただけると励みになります。

- リポジトリ: https://github.com/highdefinitionaudiodriver/InternetVotingSystem
- 連絡先: highdefinitionaudiodriver@gmail.com
