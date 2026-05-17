from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

wb = Workbook()

FONT = "Arial"
HEADER_FILL = PatternFill("solid", start_color="1F4E78")
SUBHEAD_FILL = PatternFill("solid", start_color="D9E1F2")
WARN_FILL = PatternFill("solid", start_color="FFF2CC")
RED_FILL = PatternFill("solid", start_color="FCE4D6")
GREEN_FILL = PatternFill("solid", start_color="E2EFDA")

thin = Side(border_style="thin", color="999999")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

def header(cell):
    cell.font = Font(name=FONT, bold=True, color="FFFFFF", size=11)
    cell.fill = HEADER_FILL
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = BORDER

def subhead(cell):
    cell.font = Font(name=FONT, bold=True, size=11)
    cell.fill = SUBHEAD_FILL
    cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    cell.border = BORDER

def body(cell, wrap=True):
    cell.font = Font(name=FONT, size=10)
    cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=wrap)
    cell.border = BORDER

def set_widths(ws, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

def write_table(ws, start_row, headers, rows, widths=None):
    if widths:
        set_widths(ws, widths)
    for j, h in enumerate(headers, 1):
        c = ws.cell(row=start_row, column=j, value=h)
        header(c)
    ws.row_dimensions[start_row].height = 28
    for i, row in enumerate(rows, start=start_row + 1):
        for j, val in enumerate(row, 1):
            c = ws.cell(row=i, column=j, value=val)
            body(c)
        ws.row_dimensions[i].height = max(20, 15 * max(1, max((str(v).count("\n") + len(str(v)) // 40) for v in row)))

# ============================================================
# Sheet 0: 表紙・目次
# ============================================================
ws = wb.active
ws.title = "00_表紙"
set_widths(ws, [3, 30, 70, 3])

ws["B2"] = "マイナンバーカード活用 インターネット投票システム"
ws["B2"].font = Font(name=FONT, bold=True, size=18, color="1F4E78")
ws.merge_cells("B2:C2")

ws["B3"] = "システム設計書"
ws["B3"].font = Font(name=FONT, bold=True, size=14)
ws.merge_cells("B3:C3")

meta = [
    ("バージョン", "1.0"),
    ("作成日", "2026-05-17"),
    ("対象フェーズ", "要件定義 / アーキテクチャ設計（実装は後続Codexフェーズ）"),
    ("読者", "Codex（実装エージェント）／ バックエンド・フロントエンド開発者"),
    ("準拠法令", "公職選挙法（昭和25年法律第100号）／ マイナンバー法 / 個人情報保護法"),
]
r = 5
for k, v in meta:
    a = ws.cell(row=r, column=2, value=k); subhead(a)
    b = ws.cell(row=r, column=3, value=v); body(b)
    r += 1

r += 1
ws.cell(row=r, column=2, value="目次").font = Font(name=FONT, bold=True, size=14)
r += 1
toc = [
    ("01_システム概要", "目的、設計理念、想定スケール、スコープ"),
    ("02_アーキテクチャ", "システム構成・ゾーン分離方針"),
    ("03_コンポーネント", "9つの主要コンポーネントの役割と技術選定"),
    ("04_データモデル", "ID_DB / VOTE_DB / AUDIT_LOG のスキーマ"),
    ("05_シーケンス", "投票プロセスの12ステップ"),
    ("06_暗号仕様", "暗号プリミティブ・パラメータ選定"),
    ("07_セキュリティ", "脅威モデルと対応策"),
    ("08_法令対応表", "公職選挙法条文とシステム要件の対応"),
    ("09_API定義", "コンポーネント間API一覧"),
    ("10_Codex実装指示", "実装単位分割・テスト要件"),
]
for name, desc in toc:
    a = ws.cell(row=r, column=2, value=name); body(a)
    b = ws.cell(row=r, column=3, value=desc); body(b)
    r += 1

# ============================================================
# Sheet 1: システム概要
# ============================================================
ws = wb.create_sheet("01_システム概要")
set_widths(ws, [3, 25, 70])
ws["B2"] = "1. システム概要と目的"
ws["B2"].font = Font(name=FONT, bold=True, size=14, color="1F4E78")

rows = [
    ("目的", "日本の公職選挙において、有権者が物理的な投票所に赴かずに、自宅等のインターネット環境からマイナンバーカードを用いて投票できるようにする。"),
    ("基本理念", "公職選挙法の基本原則（普通・平等・秘密・直接・自由選挙）を、物理的投票所運用の代わりに暗号学的プロトコルとシステム設計で担保する。"),
    ("想定有権者数", "約1億人"),
    ("ピーク負荷", "200万RPS（投票締切1時間前を想定）"),
    ("投票期間", "公示日翌日〜投票日20:00（複数日に渡る期日前投票相当）"),
    ("可用性目標", "99.99%（投票期間中）"),
    ("スコープ外1", "マイナンバーカードの発行・失効管理（J-LIS所管）"),
    ("スコープ外2", "選挙人名簿の本源的管理（市区町村選管所管 → 本システムはAPI連携）"),
    ("スコープ外3", "開票結果の公式公示（中央選挙管理会の責任範囲）"),
]
r = 4
for k, v in rows:
    a = ws.cell(row=r, column=2, value=k); subhead(a)
    b = ws.cell(row=r, column=3, value=v); body(b)
    ws.row_dimensions[r].height = 35
    r += 1

# ============================================================
# Sheet 2: アーキテクチャ
# ============================================================
ws = wb.create_sheet("02_アーキテクチャ")
set_widths(ws, [3, 22, 22, 65])
ws["B2"] = "2. アーキテクチャ - ゾーン構成"
ws["B2"].font = Font(name=FONT, bold=True, size=14, color="1F4E78")

headers = ["ゾーン", "配置コンポーネント", "責務と原則"]
rows = [
    ("クライアント層", "投票Webアプリ(PWA), スマホアプリ, ICカードリーダ/NFC", "ユーザーUI。投票内容の暗号化はクライアント側で完結。平文はサーバーに送出しない。"),
    ("DMZ / Edge", "WAF, DDoS防御, CDN", "外部からの攻撃緩和。静的アセット配信。"),
    ("認証ゾーン（赤）", "JPKIゲートウェイ, ブラインド署名発行サーバー, ID_DB, 選挙人名簿照合API, J-LIS連携", "個人識別を扱う。電子証明書を検証し、ブラインド署名済投票券トークンを発行。投票内容は知り得ない。"),
    ("匿名投票ゾーン（青）", "投票受付サーバー(Ballot Box), VOTE_DB, ミックスネット", "暗号化投票を受け付ける。個人情報を一切持たない。送信元IPも投票レコードに紐づけない。"),
    ("集計ゾーン（緑）", "閾値復号サーバー群, 集計サーバー, 監査ログ(WORM)", "投票締切後にt-of-n鍵共有で復号。準同型加算により候補者別票数のみを取得。"),
]
write_table(ws, 4, headers, rows, widths=[3, 22, 35, 65])

# 色分け
ws.cell(row=6, column=2).fill = RED_FILL
ws.cell(row=7, column=2).fill = SUBHEAD_FILL
ws.cell(row=8, column=2).fill = RED_FILL
ws.cell(row=9, column=2).fill = SUBHEAD_FILL
ws.cell(row=10, column=2).fill = GREEN_FILL

r = 12
ws.cell(row=r, column=2, value="重要原則").font = Font(name=FONT, bold=True, size=12, color="C00000")
r += 1
principles = [
    "認証ゾーン（赤）と匿名投票ゾーン（青）はネットワーク的に物理分離する（異なるAS / VPC / 運用主体）。",
    "両ゾーン間で授受される情報は『ブラインド署名済投票券トークン』のみ。クライアント経由でのみ転送する。",
    "サーバー間の直接通信は禁止。これによりトークンから投票者を逆引きすることが暗号学的に不可能となる。",
    "マイナンバー（12桁）はUI入力欄を設けず、APIスキーマにも定義せず、いかなる保存もしない。",
]
for p in principles:
    c = ws.cell(row=r, column=2, value="•"); body(c)
    c = ws.cell(row=r, column=3, value=p); body(c)
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=4)
    ws.row_dimensions[r].height = 30
    r += 1

# ============================================================
# Sheet 3: コンポーネント
# ============================================================
ws = wb.create_sheet("03_コンポーネント")
ws["B2"] = "3. 主要コンポーネント"
ws["B2"].font = Font(name=FONT, bold=True, size=14, color="1F4E78")

headers = ["#", "コンポーネント名", "ゾーン", "推奨実装言語", "主要責務", "重要原則"]
rows = [
    (1, "投票クライアント(Web)", "クライアント", "TypeScript + React 18", "JPKI連携、ElGamal暗号化、ブラインド署名要求、匿名チャネル送信", "投票内容の平文はクライアントメモリ外に出ない"),
    (2, "投票クライアント(Mobile)", "クライアント", "Swift / Kotlin", "NFC経由カード読取、同上", "Attestation必須（Play Integrity / App Attest）"),
    (3, "JPKI連携ゲートウェイ", "認証ゾーン", "Go / Java", "電子証明書のOCSP検証、基本4情報取得、選挙人名簿照合", "マイナンバーは取得しない。基本4情報はメモリ上のみ。"),
    (4, "ブラインド署名発行サーバー", "認証ゾーン", "Rust", "ブラインド署名による投票券トークン発行、二重発行防止", "署名対象の中身を知り得ない。HSMで秘密鍵保護。"),
    (5, "投票受付サーバー(Ballot Box)", "匿名ゾーン", "Go", "暗号化投票受付、トークン署名検証、ZKP検証、重複チェック", "送信元IP・セッション情報を投票レコードに紐づけない"),
    (6, "ミックスネット", "匿名ゾーン", "Rust", "再暗号化シャッフル（複数独立ノード）", "各ノードは異なる運用主体（中央選管/最高裁/会計検査院/第三者監査）"),
    (7, "閾値復号サーバー", "集計ゾーン", "Rust", "t-of-n鍵共有による復号", "t=5, n=7。単独機関では復号不可能"),
    (8, "集計サーバー", "集計ゾーン", "Go", "準同型加算による候補者別票数集計、結果公示", "個別票は復号しない（合算暗号文のみ復号）"),
    (9, "公開検証掲示板", "公開", "Go", "ballot_id 掲載、ミックス・復号証明の公開", "End-to-End検証可能性の担保"),
    (10, "監査ログ基盤", "集計ゾーン", "Go", "ハッシュチェーン連結のWORM保管", "改ざん不可。複数地理冗長化"),
]
write_table(ws, 4, headers, rows, widths=[3, 5, 28, 18, 25, 40, 35])

# ============================================================
# Sheet 4: データモデル
# ============================================================
ws = wb.create_sheet("04_データモデル")
ws["B2"] = "4. データモデル"
ws["B2"].font = Font(name=FONT, bold=True, size=14, color="1F4E78")

headers = ["DB", "テーブル", "カラム名", "型", "PK/制約", "説明"]
rows = [
    ("ID_DB", "voter_status", "voter_hash", "CHAR(64)", "PK", "SHA-256(証明書シリアル || 選挙ID || ソルト)"),
    ("ID_DB", "voter_status", "election_id", "VARCHAR(32)", "NOT NULL", "選挙ID"),
    ("ID_DB", "voter_status", "token_issued", "BOOLEAN", "NOT NULL", "投票券発行済フラグ。二重発行防止のキー"),
    ("ID_DB", "voter_status", "token_issued_at", "TIMESTAMP", "", "発行時刻（監査用）"),
    ("ID_DB", "voter_status", "revote_count", "INTEGER", "DEFAULT 0", "上書き投票回数（強要対策）"),
    ("ID_DB", "voter_status", "last_issued_token_hash", "CHAR(64)", "", "直近発行トークンのハッシュ"),
    ("VOTE_DB", "ballot", "ballot_id", "UUID", "PK", "ランダム生成。個人と無関係"),
    ("VOTE_DB", "ballot", "election_id", "VARCHAR(32)", "NOT NULL", "選挙ID"),
    ("VOTE_DB", "ballot", "blind_token", "BYTEA", "NOT NULL", "ブラインド署名済トークン"),
    ("VOTE_DB", "ballot", "blind_token_hash", "CHAR(64)", "UNIQUE+revote_serial", "二重投票検出用"),
    ("VOTE_DB", "ballot", "encrypted_vote", "BYTEA", "NOT NULL", "ElGamal暗号文 (c1, c2)"),
    ("VOTE_DB", "ballot", "zk_proof", "BYTEA", "NOT NULL", "候補者集合内であることのZKP"),
    ("VOTE_DB", "ballot", "received_at_bucket", "TIMESTAMP", "NOT NULL", "5分単位に丸めたタイムスタンプ"),
    ("VOTE_DB", "ballot", "sequence_in_bucket", "INTEGER", "NOT NULL", "バケット内シーケンス（順序撹乱）"),
    ("VOTE_DB", "ballot", "revote_serial", "INTEGER", "DEFAULT 1", "同一トークンの上書き連番"),
    ("AUDIT_LOG", "audit_log", "log_id", "BIGSERIAL", "PK", "ログID"),
    ("AUDIT_LOG", "audit_log", "prev_hash", "CHAR(64)", "NOT NULL", "前レコードのハッシュ"),
    ("AUDIT_LOG", "audit_log", "log_hash", "CHAR(64)", "NOT NULL", "SHA-256(prev_hash || payload)"),
    ("AUDIT_LOG", "audit_log", "component", "VARCHAR(64)", "NOT NULL", "コンポーネント名"),
    ("AUDIT_LOG", "audit_log", "event_type", "VARCHAR(64)", "NOT NULL", "イベント種別"),
    ("AUDIT_LOG", "audit_log", "payload", "JSONB", "NOT NULL", "ペイロード。個人特定情報・投票内容は含めない"),
    ("AUDIT_LOG", "audit_log", "occurred_at", "TIMESTAMP", "NOT NULL", "発生時刻"),
]
write_table(ws, 4, headers, rows, widths=[3, 12, 15, 22, 14, 20, 50])

r = ws.max_row + 2
ws.cell(row=r, column=2, value="個人情報との連結不可能性").font = Font(name=FONT, bold=True, size=12, color="C00000")
r += 1
notes = [
    "voter_status には voter_hash のみ、ballot には blind_token_hash のみが格納される。",
    "両者の対応関係はブラインド署名の数学的性質により、発行サーバーですら復元不可能。",
    "盲化因子 r がクライアント側にしか存在しないため、いかなるサーバー側操作でも紐付けは不可能。",
]
for n in notes:
    c = ws.cell(row=r, column=2, value="•"); body(c)
    c = ws.cell(row=r, column=3, value=n); body(c)
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=7)
    r += 1

# ============================================================
# Sheet 5: シーケンス
# ============================================================
ws = wb.create_sheet("05_シーケンス")
ws["B2"] = "5. 投票プロセス シーケンス"
ws["B2"].font = Font(name=FONT, bold=True, size=14, color="1F4E78")

headers = ["#", "フェーズ", "アクター", "操作", "技術的詳細"]
rows = [
    (1, "ログイン", "有権者→カード", "利用者証明用PIN(4桁)入力", "ICチップから利用者証明用電子証明書を取得"),
    (2, "ログイン", "クライアント→JPKI-GW", "ログイン要求(証明書)", "TLS 1.3 + mTLS。短命JWT発行"),
    (3, "ログイン", "JPKI-GW→J-LIS", "OCSP検証", "証明書の失効確認"),
    (4, "ログイン", "JPKI-GW→ID_DB", "voter_hash算出・選挙人名簿照合", "SHA-256(serial || election_id || salt)"),
    (5, "投票内容暗号化", "クライアント内", "候補者選択 → ElGamal暗号化", "encrypted_vote = Enc(pk_election, candidate_id)。盲化因子rで blinded 生成"),
    (6, "投票券要求", "有権者→カード", "署名用PIN(英数字6-16桁)入力", "blinded への署名 σ_blind"),
    (7, "投票券要求", "クライアント→ブラインド署名サーバ", "投票券発行要求", "BEGIN TX; SELECT token_issued FOR UPDATE"),
    (8, "投票券発行", "ブラインド署名サーバ", "ブラインド署名生成", "σ_token = sign_blind(blinded)。UPDATE token_issued=TRUE; COMMIT"),
    (9, "盲化解除", "クライアント内", "token = unblind(σ_token, r)", "encrypted_vote に対する有効な署名を得る"),
    (10, "投票送信", "クライアント→受付サーバ", "POST /ballot", "匿名チャネル経由。{encrypted_vote, token, zk_proof}"),
    (11, "投票受付", "受付サーバ", "検証 → INSERT", "token署名検証 + ZKP検証 + 重複チェック。revote_serialインクリメント"),
    (12, "受領証発行", "受付サーバ→クライアント", "ballot_id ハッシュ返却", "個人と非紐付け。公開掲示板で確認可能"),
    ("―", "===== 投票期間終了 =====", "", "", ""),
    (13, "ミックス", "ミックスネット", "再暗号化シャッフル(N回)", "各独立運用ノードで順次"),
    (14, "復号", "閾値復号サーバ群", "t-of-n 鍵共有者集合", "5-of-7。準同型加算後の合算暗号文を復号"),
    (15, "集計", "集計サーバ", "候補者別票数算出 → 公示", "監査ログにハッシュチェーン記録"),
]
write_table(ws, 4, headers, rows, widths=[3, 5, 18, 22, 28, 60])

# ============================================================
# Sheet 6: 暗号仕様
# ============================================================
ws = wb.create_sheet("06_暗号仕様")
ws["B2"] = "6. 暗号プリミティブ"
ws["B2"].font = Font(name=FONT, bold=True, size=14, color="1F4E78")

headers = ["用途", "アルゴリズム", "パラメータ", "推奨ライブラリ", "備考"]
rows = [
    ("投票内容暗号化", "Exponential ElGamal（楕円曲線版）", "secp256r1 または Curve25519/ristretto255", "curve25519-dalek (Rust), noble-curves (TS)", "準同型加算性質を利用"),
    ("ブラインド署名", "RSA Blind Signature", "RSA-3072 / SHA-384 (RFC 9474)", "RustCrypto/RSA", "投票券トークン発行用"),
    ("鍵共有", "Shamir閾値秘密分散 + DKG", "t=5, n=7", "vsss-rs / FROST", "選挙公開鍵生成"),
    ("ゼロ知識証明", "非対話型シグマプロトコル (Chaum-Pedersen)", "Fiat-Shamir変換", "dalek-cryptography/zkp", "候補者集合内であることの証明"),
    ("通信路", "TLS 1.3 + mTLS", "X25519 / AES-256-GCM", "rustls / BoringSSL", "PFS必須"),
    ("ハッシュ", "SHA-256 / SHA-3-256", "ソルト32バイト", "ring / sha2", "voter_hash算出等"),
    ("クライアント秘密鍵保護", "マイナンバーカードICチップ", "JPKI仕様準拠", "JPKI公式SDK", "外部抽出不可"),
    ("監査ログ", "ハッシュチェーン", "SHA-256", "ring / sha2", "WORM保管"),
]
write_table(ws, 4, headers, rows, widths=[3, 25, 30, 35, 35, 30])

r = ws.max_row + 2
ws.cell(row=r, column=2, value="鍵管理機関構成（t=5, n=7）").font = Font(name=FONT, bold=True, size=12)
r += 1
holders = [
    "①中央選挙管理会", "②最高裁判所", "③会計検査院",
    "④総務省", "⑤独立第三者監査機関A", "⑥独立第三者監査機関B", "⑦市民選出委員会",
]
for h in holders:
    c = ws.cell(row=r, column=2, value=h); body(c)
    r += 1

# ============================================================
# Sheet 7: セキュリティ脅威モデル
# ============================================================
ws = wb.create_sheet("07_セキュリティ")
ws["B2"] = "7. セキュリティ脅威モデル"
ws["B2"].font = Font(name=FONT, bold=True, size=14, color="1F4E78")

headers = ["#", "脅威", "影響範囲", "発生可能性", "対応策", "残存リスク"]
rows = [
    (1, "クライアントマルウェアによる投票内容窃取", "個別有権者", "中", "カード内秘密鍵は抽出不可", "画面改ざんによる投票先操作 → 上書き投票で緩和"),
    (2, "受付サーバー管理者による票閲覧", "全票", "低", "ElGamal暗号文。閾値復号鍵なしでは解読不可", "なし"),
    (3, "認証DBダンプ流出", "個人識別情報", "低", "投票内容は含まれない。voter_hashはソルト付", "選挙横断的な名寄せ不可"),
    (4, "投票DBダンプ流出", "暗号化票", "低", "個人情報を一切持たない。暗号文は閾値鍵なしで解読不可", "なし"),
    (5, "二重投票", "選挙結果", "中", "SELECT FOR UPDATE + blind_token_hash UNIQUE + revote_serial", "なし"),
    (6, "DoS / DDoS攻撃", "可用性", "高", "WAF + Anycast CDN + レート制限 + 投票期間長期化", "ボット対策との両立が課題"),
    (7, "内部関係者による集計改ざん", "選挙結果", "低", "閾値復号 + 公開検証可能性 + ハッシュチェーン監査ログ", "5機関以上の共謀があれば理論上可能"),
    (8, "マイナンバー漏洩", "プライバシー", "ゼロ", "そもそも取得・保持・通信しない設計", "なし（設計上発生し得ない）"),
    (9, "投票強要・買収", "自由意思", "中", "上書き投票機能により最終票のみ有効。公開掲示板で本人のみ確認可", "強要者の前で『正しい』暗号文を見せる攻撃 → ZKPで対応"),
    (10, "ミックスネットノードの結託", "匿名性", "低", "各ノード異なる運用主体。1ノードでも誠実なら匿名性保持", "全N機関の共謀があれば理論上可能"),
    (11, "クライアントPKI改ざん", "なりすまし", "低", "Subresource Integrity + Service Worker署名検証 + Mobile Attestation", "OS自体の侵害は対象外"),
    (12, "選挙人名簿API攻撃", "選挙権侵害", "低", "選管との相互mTLS + 二重照合", "選管側の侵害は対象外"),
]
write_table(ws, 4, headers, rows, widths=[3, 5, 35, 18, 12, 45, 35])

# 残存リスク列を着色
for i in range(5, 5 + len(rows)):
    ws.cell(row=i, column=7).fill = WARN_FILL

# ============================================================
# Sheet 8: 法令対応表
# ============================================================
ws = wb.create_sheet("08_法令対応表")
ws["B2"] = "8. 公職選挙法 ↔ システム要件 対応表"
ws["B2"].font = Font(name=FONT, bold=True, size=14, color="1F4E78")

headers = ["条文", "原則", "システム上の担保", "実装担当コンポーネント", "検証方法"]
rows = [
    ("公選法第9条", "選挙権（年齢・国籍要件）", "JPKI基本4情報 + 選挙人名簿API照合で年齢・住所要件を判定", "jpki-gateway", "ユニットテスト + 選管連携テスト"),
    ("公選法第11条", "選挙権を有しない者", "選管管理の欠格者リストとの突合", "jpki-gateway", "選管連携テスト"),
    ("公選法第36条", "一人一票", "voter_status.token_issued の FOR UPDATE排他制御 + blind_token_hash UNIQUE制約", "blind-signer, ballot-box", "並行性テスト（10万並列）"),
    ("公選法第42条", "選挙人名簿登録者のみ投票可", "JPKIゲートウェイで選挙人名簿照合API呼出", "jpki-gateway", "選管連携テスト"),
    ("公選法第44条", "投票所投票主義（→本システムで代替）", "投票クライアントを『電子投票所』と定義", "client-web/mobile", "セキュリティ監査"),
    ("公選法第46条", "秘密投票", "①クライアント側ElGamal暗号化 ②ブラインド署名 ③ミックスネット ④閾値復号 ⑤DB物理分離", "全体", "暗号プロトコル形式検証 + プロパティベーステスト"),
    ("公選法第48条の2", "期日前投票", "投票期間中いつでも投票可能。上書き投票で強要対策も兼ねる", "ballot-box", "受入テスト"),
    ("公選法第49条", "不在者投票", "居所に関わらず投票可能。海外有権者にも適用可能", "client-web/mobile", "受入テスト"),
    ("公選法第50条", "投票所での投票拒否（二重投票防止）", "token_issued=TRUE 時に物理投票所と相互排他API連携", "jpki-gateway", "選管連携テスト"),
    ("公選法第52条", "投票の秘密侵害禁止", "内部監査ログにも個人と票の対応は記録不可。アクセス監視SIEM", "audit-log", "ログレビュー + SIEM運用"),
    ("公選法第55条", "投票箱の閉鎖", "投票期間終了時刻にVOTE_DBをread-onlyに切替。DB権限でINSERT不可", "ballot-box, vote-db", "切替動作テスト"),
    ("公選法第66条", "開票", "閾値復号 + 集計サーバーで自動化。立会人は閾値鍵共有者として参加", "threshold-decryptor, tally", "復号セレモニー演習"),
    ("公選法第68条", "無効投票", "ZKP検証失敗・形式不正は無効として別カウント", "ballot-box, tally", "境界値テスト"),
    ("公選法第205条", "選挙の効力に関する異議", "E2E検証可能性により第三者が再計算可能。AUDIT_LOG（WORM）で証拠保全", "bulletin-board, audit-log", "外部監査"),
    ("公選法第221-225条", "買収・投票強要罪", "上書き投票で書き換え可能とすることで強要を実効性のないものに", "ballot-box", "脅威モデル評価"),
    ("マイナンバー法第19条", "個人番号の利用制限", "個人番号を一切取得しない設計により本条の適用外", "全体（UI・APIスキーマ）", "OpenAPI Linterによる強制 + UIレビュー"),
    ("個人情報保護法", "目的外利用禁止・最小収集", "基本4情報はメモリ上のみで利用、永続化禁止", "jpki-gateway", "コードレビュー + DPIA"),
]
write_table(ws, 4, headers, rows, widths=[3, 22, 30, 50, 28, 30])

# ============================================================
# Sheet 9: API定義
# ============================================================
ws = wb.create_sheet("09_API定義")
ws["B2"] = "9. コンポーネント間API一覧"
ws["B2"].font = Font(name=FONT, bold=True, size=14, color="1F4E78")

headers = ["#", "API名", "プロトコル", "送信元", "受信先", "メソッド/パス", "リクエスト概要", "レスポンス概要"]
rows = [
    (1, "ログイン", "HTTPS+mTLS", "client", "jpki-gateway", "POST /api/v1/auth/login", "{ user_cert: <利用者証明用証明書> }", "{ session_jwt, election_id }"),
    (2, "選挙人名簿照合", "gRPC (mTLS)", "jpki-gateway", "選管API", "VoterRegistry.Lookup", "{ basic_info_hash, election_id }", "{ eligible: bool, district_id }"),
    (3, "投票券発行要求", "HTTPS", "client", "blind-signer", "POST /api/v1/token/issue", "{ blinded_message, user_cert, signature }", "{ blind_signature }"),
    (4, "投票送信", "HTTPS（匿名チャネル経由）", "client", "ballot-box", "POST /api/v1/ballot", "{ encrypted_vote, token, zk_proof }", "{ ballot_id_hash }"),
    (5, "受領確認", "HTTPS", "client", "bulletin-board", "GET /api/v1/board/{ballot_id_hash}", "ballot_id_hash", "{ recorded: bool, timestamp_bucket }"),
    (6, "投票締切→DB凍結", "内部cron", "scheduler", "vote-db", "ALTER ROLE ... SET default_transaction_read_only=on", "なし", "なし"),
    (7, "ミックスネット投入", "gRPC", "ballot-box", "mixnet-node-1", "Mixnet.Shuffle", "{ ciphertexts[] }", "{ shuffled_ciphertexts[], proof }"),
    (8, "閾値復号", "gRPC (mTLS)", "tally", "threshold-decryptor", "Decryptor.PartialDecrypt", "{ aggregated_ciphertext, share_id }", "{ partial_decryption, proof }"),
    (9, "結果公示", "HTTPS", "tally", "bulletin-board", "POST /api/v1/board/result", "{ per_candidate_counts, mix_proofs, decrypt_proofs }", "{ committed_hash }"),
    (10, "監査ログ書込", "gRPC (内部)", "全コンポーネント", "audit-log", "AuditLog.Append", "{ component, event_type, payload }", "{ log_id, log_hash }"),
]
write_table(ws, 4, headers, rows, widths=[3, 5, 22, 28, 22, 22, 32, 40, 32])

# ============================================================
# Sheet 10: Codex実装指示
# ============================================================
ws = wb.create_sheet("10_Codex実装指示")
ws["B2"] = "10. Codex実装フェーズへの引き継ぎ"
ws["B2"].font = Font(name=FONT, bold=True, size=14, color="1F4E78")

headers = ["#", "モジュール名", "言語", "主要依存ライブラリ", "実装責務", "成果物", "テスト要件"]
rows = [
    (1, "jpki-gateway", "Go", "go-jose/v3, grpc-go", "JPKI連携、選挙人照合、セッション発行", "RESTサーバ + Dockerイメージ", "JPKIモック統合テスト"),
    (2, "blind-signer", "Rust", "rsa, blind-rsa-signatures, vsss-rs", "ブラインド署名発行、二重発行防止", "gRPCサーバ + HSM連携", "並行性テスト10万並列"),
    (3, "ballot-box", "Go", "go-ristretto, gnark", "投票受付、ZKP検証、重複チェック", "RESTサーバ", "ZKP検証プロパティテスト"),
    (4, "mixnet-node", "Rust", "curve25519-dalek, ed25519-dalek", "再暗号化シャッフル + 正当性証明", "gRPCサーバ（複数インスタンス）", "1000万票シャッフルベンチ"),
    (5, "threshold-decryptor", "Rust", "frost-ristretto255", "閾値復号、部分復号証明", "gRPCサーバ + HSM連携", "復号セレモニー演習"),
    (6, "tally", "Go", "go-ristretto", "準同型加算集計、結果公示", "RESTサーバ", "選挙データセット回帰テスト"),
    (7, "client-web", "TypeScript + React 18", "noble-curves, @scure/base, jpki-web-sdk", "PWA、JPKI連携、暗号化、匿名送信", "PWAビルド成果物", "Cypress E2E + 暗号プロパティテスト"),
    (8, "client-mobile", "Swift / Kotlin", "JPKI公式SDK, CryptoKit / Tink", "ネイティブアプリ、NFCカード読取", "iOS/Android アプリ", "実機テスト + Attestation検証"),
    (9, "bulletin-board", "Go", "boltdb / postgres", "公開掲示板、検証用ログ公開", "RESTサーバ", "公開検証ツール提供"),
    (10, "audit-log", "Go", "postgres, ring", "ハッシュチェーン監査ログ、WORM保管", "RESTサーバ + 冗長化基盤", "改ざん検知テスト"),
]
write_table(ws, 4, headers, rows, widths=[3, 5, 22, 22, 38, 32, 28, 28])

r = ws.max_row + 2
ws.cell(row=r, column=2, value="実装時の必須遵守事項").font = Font(name=FONT, bold=True, size=12, color="C00000")
r += 1
rules = [
    "暗号アルゴリズムの独自実装を禁止する。枯れたライブラリのみを使用する。",
    "各モジュール間IFはOpenAPI 3.1 / Protocol Buffersで先行定義し、ピン留めする。",
    "APIスキーマに `mynumber`, `personal_number`, `個人番号` 等のフィールドを定義してはならない（CIで自動検出）。",
    "voter_hash は必ず election_id 単位でソルトを変える（選挙横断的な名寄せ防止）。",
    "VOTE_DB のスキーマには voter 関連カラムを追加してはならない（DBレビュー必須）。",
    "全コンポーネントはステートレス設計とし、AUDIT_LOG への書込は同期トランザクションで行う。",
    "クライアントは投票確定前に確認画面を必ず表示し、再リチャレンジ可能とする（強要対策）。",
    "プロダクションビルドではデバッグログを完全に削除（ビルドフラグで制御）。",
]
for rule in rules:
    c = ws.cell(row=r, column=2, value="●"); body(c)
    c = ws.cell(row=r, column=3, value=rule); body(c)
    ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=9)
    ws.row_dimensions[r].height = 30
    r += 1

# Save
out = r"G:\マイドライブ\claudecode\InternetVotingSystem\InternetVotingSystem_DesignDoc.xlsx"
wb.save(out)
print(f"Saved: {out}")
