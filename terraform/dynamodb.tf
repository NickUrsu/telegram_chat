resource "aws_dynamodb_table" "food_logs" {
  name         = "food_logs"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "user_id"
  range_key = "timestamp"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  tags = local.common_tags
}

resource "aws_dynamodb_table" "user_profiles" {
  name         = "user_profiles"
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  tags = local.common_tags
}

resource "aws_dynamodb_table" "sessions" {
  name         = "sessions"
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "user_id"

  attribute {
    name = "user_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = local.common_tags
}

