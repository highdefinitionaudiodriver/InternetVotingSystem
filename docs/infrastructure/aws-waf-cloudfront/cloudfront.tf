# CloudFront distribution + WAF log delivery for the InternetVotingSystem.
#
# This file is opt-in: nothing here is created unless `var.create_distribution`
# is true, so the original WAF-only sample remains the minimal, easily-audited
# starting point. When set to true the module additionally provisions:
#
#   - aws_cloudfront_distribution.api: edge in front of the API origin, with
#     the existing WAF Web ACL attached and the cache disabled for /elections
#     and /audit-log so cast-as-intended verification and rate limiting are
#     not undermined by edge caching.
#   - aws_kinesis_firehose_delivery_stream.waf_logs: WAF -> Firehose -> S3
#     bucket. The S3 bucket has Object Lock (compliance mode) so the audit
#     trail of WAF decisions is itself WORM-protected, mirroring the audit
#     log posture inside the API.
#
# Privacy invariants enforced here:
#   - sampled_requests_enabled stays false on the Web ACL (preserves the
#     no-request-body-in-CloudWatch posture).
#   - WAF logging redacts the Authorization header and `certificate_serial`
#     query string in case they ever appear, in addition to the existing
#     posture of never sending Authorization through the front door.

variable "create_distribution" {
  type        = bool
  description = "When true, provision the CloudFront distribution + WAF logging stack."
  default     = false
}

variable "api_origin_domain_name" {
  type        = string
  description = "Origin domain name (e.g. ivs-api.internal.example.com) that the distribution forwards to."
  default     = ""
}

variable "waf_log_bucket_name" {
  type        = string
  description = "S3 bucket name receiving WAF logs via Kinesis Firehose. Will be created."
  default     = ""
}

variable "waf_log_retention_days" {
  type        = number
  description = "Object Lock retention period (days) for the WAF log bucket."
  default     = 365
}

# ----- CloudFront -----------------------------------------------------------

resource "aws_cloudfront_distribution" "api" {
  count = var.create_distribution ? 1 : 0

  enabled         = true
  is_ipv6_enabled = true
  comment         = "${var.name_prefix} InternetVotingSystem edge"
  web_acl_id      = aws_wafv2_web_acl.this.arn
  price_class     = "PriceClass_200"

  origin {
    origin_id                = "api"
    domain_name              = var.api_origin_domain_name
    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "api"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    # Disable edge caching for every dynamic path. The bulletin board and
    # receipt endpoints in particular MUST hit the origin so the audit log
    # records the access and so cache poisoning is impossible.
    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0

    forwarded_values {
      query_string = true
      headers      = ["Authorization", "Content-Type", "Accept", "X-Forwarded-For"]
      cookies {
        forward = "none"
      }
    }
  }

  # The static web client is safe to cache aggressively.
  ordered_cache_behavior {
    path_pattern           = "/static/*"
    target_origin_id       = "api"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    default_ttl            = 3600
    max_ttl                = 86400
    min_ttl                = 0

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = local.common_tags
}

# ----- S3 bucket (Object Lock / WORM) ---------------------------------------

resource "aws_s3_bucket" "waf_logs" {
  count  = var.create_distribution ? 1 : 0
  bucket = var.waf_log_bucket_name

  # Object Lock can only be enabled at creation; this stays opt-in.
  object_lock_enabled = true

  tags = local.common_tags
}

resource "aws_s3_bucket_public_access_block" "waf_logs" {
  count                   = var.create_distribution ? 1 : 0
  bucket                  = aws_s3_bucket.waf_logs[0].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_object_lock_configuration" "waf_logs" {
  count  = var.create_distribution ? 1 : 0
  bucket = aws_s3_bucket.waf_logs[0].id

  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = var.waf_log_retention_days
    }
  }
}

resource "aws_s3_bucket_versioning" "waf_logs" {
  count  = var.create_distribution ? 1 : 0
  bucket = aws_s3_bucket.waf_logs[0].id
  versioning_configuration {
    status = "Enabled"
  }
}

# ----- Kinesis Firehose -> S3 ----------------------------------------------

resource "aws_iam_role" "firehose" {
  count = var.create_distribution ? 1 : 0
  name  = "${var.name_prefix}-waf-firehose"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "firehose.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy" "firehose_s3" {
  count = var.create_distribution ? 1 : 0
  name  = "${var.name_prefix}-waf-firehose-s3"
  role  = aws_iam_role.firehose[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:AbortMultipartUpload",
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:ListBucketMultipartUploads",
          "s3:PutObject"
        ]
        Resource = [
          aws_s3_bucket.waf_logs[0].arn,
          "${aws_s3_bucket.waf_logs[0].arn}/*"
        ]
      }
    ]
  })
}

resource "aws_kinesis_firehose_delivery_stream" "waf_logs" {
  count       = var.create_distribution ? 1 : 0
  # WAFv2 requires the stream name to begin with "aws-waf-logs-".
  name        = "aws-waf-logs-${var.name_prefix}"
  destination = "extended_s3"

  extended_s3_configuration {
    role_arn        = aws_iam_role.firehose[0].arn
    bucket_arn      = aws_s3_bucket.waf_logs[0].arn
    buffering_size  = 5
    buffering_interval = 60
    compression_format = "GZIP"
    prefix             = "waf/year=!{timestamp:yyyy}/month=!{timestamp:MM}/day=!{timestamp:dd}/"
    error_output_prefix = "errors/!{firehose:error-output-type}/"
  }

  tags = local.common_tags
}

# ----- WAF -> Firehose wiring + redactions ----------------------------------

resource "aws_wafv2_web_acl_logging_configuration" "this" {
  count                   = var.create_distribution ? 1 : 0
  log_destination_configs = [aws_kinesis_firehose_delivery_stream.waf_logs[0].arn]
  resource_arn            = aws_wafv2_web_acl.this.arn

  redacted_fields {
    single_header {
      name = "authorization"
    }
  }
  redacted_fields {
    single_header {
      name = "cookie"
    }
  }
  redacted_fields {
    single_query_argument {
      name = "certificate_serial"
    }
  }
}
