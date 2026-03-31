variable "region" {
  description = "AWS region"
  type        = string
  default     = "ap-northeast-1"
}

variable "project_name" {
  description = "Project name used for tagging and naming"
  type        = string
  default     = "telegram-food-bot"
}

variable "environment" {
  description = "Environment name (dev, prod, etc.)"
  type        = string
  default     = "dev"
}

variable "owner" {
  description = "Resource owner"
  type        = string
  default     = "nick_ursu"
}
