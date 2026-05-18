output "web_acl_arn" {
  description = "ARN to assign to a CloudFront distribution's web_acl_id."
  value       = aws_wafv2_web_acl.this.arn
}

output "web_acl_id" {
  description = "AWS WAFv2 Web ACL ID."
  value       = aws_wafv2_web_acl.this.id
}
