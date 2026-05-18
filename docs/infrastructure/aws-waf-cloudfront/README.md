# AWS WAF + CloudFront Terraform Sample

CloudFrontに紐付けるWAFv2 Web ACLのサンプルです。`scope = "CLOUDFRONT"` のため、Terraform実行リージョンは `us-east-1` を使います。

## 使い方

```bash
terraform init
terraform plan \
  -var='name_prefix=ivs-staging' \
  -var='api_rate_limit_per_5_min=2000'
```

作成後、CloudFront Distributionに次を設定します。

```hcl
web_acl_id = module.ivs_waf.web_acl_arn
```

## ルール

- AWS IP reputation list
- AWS anonymous IP list
- AWS common rule set
- AWS known bad inputs
- `/elections/*`, `/audit-log*`, `/metrics` 向けIP単位rate limit

`enable_count_mode = true` にすると、管理ルールとrate limitをブロックせず観測できます。初期導入時はcount modeで数日観測し、投票者・監視スクレーパ・負荷試験の正常リクエストを誤検知しないことを確認してください。

## プライバシー

このサンプルはWAFで投票本文の意味解析をしません。WAFログを有効化する場合も、本文ログ、Cookie、Authorizationヘッダ、JPKI連携由来の個人識別子を保存しない設定を別途適用してください。
