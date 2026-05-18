# Infrastructure Samples

このディレクトリは、本番化検討時に必要になる周辺インフラのサンプルです。

現時点では、API/WebをCloudFrontの背後に置き、AWS WAFv2で基本的なエッジ防御を行うTerraform例を置いています。プロトタイプ本体はまだ本番暗号、JPKI実接続、WORM監査基盤を持たないため、このIaCだけで本番利用可能になるわけではありません。

## 方針

- WAF/CDNでは、IP、パス、HTTPメソッド、ヘッダ、レートを中心に制御する。
- 票本文、候補者別集計、受領証、監査ログ本文など、投票秘密や投票傾向につながる値をWAFログへ積極的に出さない。
- `/health` と `/metrics` はWAFで保護しつつ、監視元IPの許可リストや内部ネットワーク制御と組み合わせる。
- API内の in-process rate limit は最終防御であり、WAF/CDN側のレート制限を前段に置く。

## 含まれる例

- `aws-waf-cloudfront/`
  - CloudFront用 `aws_wafv2_web_acl`
  - IP reputation / anonymous IP / common rule / known bad input のAWS管理ルール
  - APIパス向けIPベースrate limit
  - 監視で使うためのWeb ACL ARN output

## 適用前の注意

1. `terraform.tfvars` で `name_prefix` とレート上限を環境に合わせる。
2. CloudFront Distribution側の `web_acl_id` に、このモジュールの `web_acl_arn` を設定する。
3. WAFログを有効化する場合は、ログ保存先の暗号化・保持期間・アクセス権を別途定義する。
4. 本番ではWAFのブロック前に `count` モードで観測期間を設け、正当な投票者を巻き込まない閾値を決める。
