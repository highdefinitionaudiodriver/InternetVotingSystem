# Claude Code / Codex 引き継ぎ資料

最終更新: 2026-05-17 (Claude Code セッション 2 終了時)

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
- インメモリRepository: `services/api/internet_voting_system/repository.py`
- SQLite Repository: `services/api/internet_voting_system/sqlite_repository.py` （NEW）
- Webクライアント: `client-web/`
  - 受領証検証パネル・監査ログ整合性チェックパネルを追加
- API定義: `docs/api/openapi.yaml`
  - 全エンドポイントのレスポンススキーマ追加
  - エラー応答 `{error:{code,message}}` 統一スキーマ追加
- テスト: `services/api/tests/`
  - `test_voting_service.py` （既存4件）
  - `test_audit_and_receipts.py` （NEW、4件）
  - `test_sqlite_repository.py` （NEW、5件）
  - 計13件すべてパス

### 新エンドポイント

- `GET /elections/{id}/receipts/{receipt_hash}`
  - 受領証検証。Cast-as-Intended / Recorded-as-Cast を担保
  - サーバ側で再計算した receipt_hash と integrity_ok フラグを返す
  - voter_hash や accepted_candidate_id は応答に含めない
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
9667200 Add Claude Code handoff guide
953dd88 Implement internet voting prototype
1411684 1st commit
```

セッション 2 のコミットはこれから作成する想定。コミットメッセージ案:

```text
Add SQLite repository, receipt verification, audit-chain integrity
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
Ran 13 tests
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
壊さないこと。OpenAPI Linter にも同じルールを将来追加する予定。

## 次の推奨作業（優先順）

1. **PostgreSQLバックエンド**: `sqlite_repository.py` のスキーマを参考に、psycopg2/psycopgでPG実装を追加。`BEGIN IMMEDIATE` を `SELECT ... FOR UPDATE` に置き換える。
2. **FastAPI移行**: 標準ライブラリHTTPサーバーは並行性能と型付けに弱い。FastAPI＋Pydantic化し、OpenAPI を自動生成に切り替える。
3. **暗号ライブラリの実装差し替え**: `DemoCryptoSuite` のインターフェースを保ったまま、`blind-rsa-signatures` (Rust経由) ＋ `ristretto255` ベースのElGamal実装に置換。Pythonからは PyO3 バインディング or subprocess で呼ぶ。
4. **Webクライアントの強化**:
   - 公開掲示板の検索フィルター（receipt_hash部分一致）
   - 候補者ごとの色分け
   - 監査ログのテーブル表示
5. **OpenAPI Linter**: `mynumber` 等を禁止するカスタムルールを Spectral で追加し、CIに組み込む。
6. **負荷試験**: `services/api` に対し、トークン発行→投票送信のフルフローを並列でぶつける負荷試験スクリプトを `tools/loadtest.py` として追加する。SQLiteは並行書き込みでロックが発生するので、上限を計測してドキュメント化。
7. **コンテナ化**: 各バックエンドを Dockerfile 化。`docker-compose.yml` で `api + nginx + sqlite volume` の最小構成を提供。

## 既知の制約

- `--storage sqlite` でホストを跨いだ複数プロセス運用は安全ではない（WALだが書き込みは直列）。本番では PostgreSQL 必須。
- `verify_audit_chain` は現状すべてのログを読み出して再計算する。エントリ数が1000万を超える場合はチェックポイント方式に変更する必要がある。
- Webクライアントはまだ JPKI のローカル署名は行わず、`certificate_serial` を入力する簡易フローのみ。本番のWeb版は JPKI ブラウザ拡張、モバイル版は NFC SDK を組み込む必要がある。
