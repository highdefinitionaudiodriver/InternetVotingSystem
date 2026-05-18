output "web_acl_arn" {
  description = "ARN to assign to a CloudFront distribution's web_acl_id."
  value       = aws_wafv2_web_acl.this.arn
}

output "web_acl_id" {
  description = "AWS WAFv2 Web ACL ID."
  value       = aws_wafv2_web_acl.this.id
}

output "cloudfront_domain_name" {
  description = "DNS name of the optional CloudFront distribution (null when create_distribution=false)."
  value       = try(aws_cloudfront_distribution.api[0].domain_name, null)
}

output "waf_log_bucket_name" {
  description = "S3 bucket name receiving WAF logs (null when create_distribution=false)."
  value       = try(aws_s3_bucket.waf_logs[0].bucket, null)
}

output "waf_log_firehose_arn" {
  description = "ARN of the Kinesis Firehose delivery stream WAF logs are routed through."
  value       = try(aws_kinesis_firehose_delivery_stream.waf_logs[0].arn, null)
}
