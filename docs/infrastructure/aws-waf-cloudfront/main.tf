terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

locals {
  common_tags = merge(
    {
      Project     = "InternetVotingSystem"
      Environment = var.environment
      ManagedBy   = "Terraform"
    },
    var.tags,
  )
}

resource "aws_wafv2_web_acl" "this" {
  name        = "${var.name_prefix}-edge-waf"
  description = "Edge WAF for InternetVotingSystem CloudFront distributions."
  scope       = "CLOUDFRONT"

  default_action {
    allow {}
  }

  rule {
    name     = "aws-ip-reputation"
    priority = 10

    override_action {
      dynamic "count" {
        for_each = var.enable_count_mode ? [1] : []
        content {}
      }
      dynamic "none" {
        for_each = var.enable_count_mode ? [] : [1]
        content {}
      }
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAmazonIpReputationList"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name_prefix}-ip-reputation"
      sampled_requests_enabled   = false
    }
  }

  rule {
    name     = "aws-anonymous-ip"
    priority = 20

    override_action {
      dynamic "count" {
        for_each = var.enable_count_mode ? [1] : []
        content {}
      }
      dynamic "none" {
        for_each = var.enable_count_mode ? [] : [1]
        content {}
      }
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAnonymousIpList"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name_prefix}-anonymous-ip"
      sampled_requests_enabled   = false
    }
  }

  rule {
    name     = "aws-common"
    priority = 30

    override_action {
      dynamic "count" {
        for_each = var.enable_count_mode ? [1] : []
        content {}
      }
      dynamic "none" {
        for_each = var.enable_count_mode ? [] : [1]
        content {}
      }
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name_prefix}-common"
      sampled_requests_enabled   = false
    }
  }

  rule {
    name     = "aws-known-bad-inputs"
    priority = 40

    override_action {
      dynamic "count" {
        for_each = var.enable_count_mode ? [1] : []
        content {}
      }
      dynamic "none" {
        for_each = var.enable_count_mode ? [] : [1]
        content {}
      }
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name_prefix}-known-bad-inputs"
      sampled_requests_enabled   = false
    }
  }

  rule {
    name     = "api-rate-limit"
    priority = 100

    action {
      dynamic "count" {
        for_each = var.enable_count_mode ? [1] : []
        content {}
      }
      dynamic "block" {
        for_each = var.enable_count_mode ? [] : [1]
        content {}
      }
    }

    statement {
      rate_based_statement {
        limit              = var.api_rate_limit_per_5_min
        aggregate_key_type = "IP"

        scope_down_statement {
          or_statement {
            statement {
              byte_match_statement {
                field_to_match {
                  uri_path {}
                }
                positional_constraint = "STARTS_WITH"
                search_string         = "/elections/"
                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
              }
            }
            statement {
              byte_match_statement {
                field_to_match {
                  uri_path {}
                }
                positional_constraint = "STARTS_WITH"
                search_string         = "/audit-log"
                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
              }
            }
            statement {
              byte_match_statement {
                field_to_match {
                  uri_path {}
                }
                positional_constraint = "EXACTLY"
                search_string         = "/metrics"
                text_transformation {
                  priority = 0
                  type     = "NONE"
                }
              }
            }
          }
        }
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.name_prefix}-api-rate-limit"
      sampled_requests_enabled   = false
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.name_prefix}-edge-waf"
    sampled_requests_enabled   = false
  }

  tags = local.common_tags
}
