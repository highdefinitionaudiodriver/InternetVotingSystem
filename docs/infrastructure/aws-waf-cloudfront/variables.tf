variable "name_prefix" {
  type        = string
  description = "Prefix used for WAF resources and CloudWatch metric names."
}

variable "environment" {
  type        = string
  description = "Deployment environment tag, such as staging or production."
  default     = "staging"
}

variable "api_rate_limit_per_5_min" {
  type        = number
  description = "Maximum requests per source IP over a rolling 5-minute WAF window for API paths."
  default     = 2000
}

variable "enable_count_mode" {
  type        = bool
  description = "When true, rules count matches instead of blocking. Use this during tuning."
  default     = true
}

variable "tags" {
  type        = map(string)
  description = "Additional tags to attach to WAF resources."
  default     = {}
}
