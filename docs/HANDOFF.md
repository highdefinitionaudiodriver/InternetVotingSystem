# Claude Code 引き継ぎ資料

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

## 現在の実装状況

初期実装として、外部依存を増やさず標準ライブラリ中心で動くローカルプロトタイプを実装済み。

- APIサーバー: `services/api/internet_voting_system/app.py`
- ドメインサービス: `services/api/internet_voting_system/service.py`
- デモ暗号境界: `services/api/internet_voting_system/crypto.py`
- インメモリRepository: `services/api/internet_voting_system/repository.py`
- Webクライアント: `client-web/`
- API定義: `docs/api/openapi.yaml`
- テスト: `services/api/tests/test_voting_service.py`

直近コミット:

```text
953dd88 Implement internet voting prototype
```

## 実行方法

API:

```powershell
Set-Location C:\Users\highd\Documents\Github\InternetVotingSystem\services\api
& 'C:\Users\highd\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m internet_voting_system.app --host 127.0.0.1 --port 8787
```

Webクライアント:

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
Ran 4 tests
OK
```

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
  'C:\Users\highd\Documents\Github\InternetVotingSystem\docs' `
  -Destination 'G:\マイドライブ\claudecode\InternetVotingSystem' -Recurse -Force
```

同期後、`__pycache__` や `.pyc` が混入していないことを確認する。

## 設計上の注意

現在の暗号実装は本番暗号ではなく、API境界と投票フローを確認するためのデモ実装である。

本番化時は `DemoCryptoSuite` を以下に置き換える。

- RFC 9474準拠のRSA Blind Signature
- ElGamal/ristretto255 による投票内容暗号化
- 候補者集合内であることのZKP
- DKGとShamir閾値復号
- JPKI/J-LIS照会と選挙人名簿APIの実接続
- WORMまたは改ざん耐性を持つ監査ログ基盤

設計書では、上書き投票について補正済み。

- `token_issued` は再発行禁止フラグではなく、過去に1回以上発行済みであることを示す監査フラグ。
- 同一トークンで再投票した場合は `revote_serial` 最大の票を採用する。
- 新トークン再発行を本格実装する場合、匿名投票ゾーンへ `voter_hash` を渡さず、認証ゾーン内で有効/失効トークンリストを作る。

## 次の推奨作業

1. 永続化層をSQLiteまたはPostgreSQLに切り替える。
2. APIサーバーを標準ライブラリHTTPからFastAPIまたはGoへ移行する。
3. `DemoCryptoSuite` のインターフェースを保ったまま、暗号ライブラリ実装へ置換する。
4. OpenAPIにレスポンススキーマとエラー形式を追加する。
5. Webクライアントに受領証検索と公開掲示板の検証画面を追加する。
