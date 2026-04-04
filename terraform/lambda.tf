resource "aws_lambda_function" "bot" {
  function_name = "${var.project_name}-handler"
  role          = aws_iam_role.lambda_role.arn
  handler = "src.handler.lambda_handler"
  runtime       = "python3.11"

 filename         = "${path.module}/lambda_build/lambda.zip"
  timeout       = 60
  memory_size   = 512
  source_code_hash = filebase64sha256("${path.module}/lambda_build/lambda.zip")

environment {
    variables = {
      DYNAMODB_TABLE        = aws_dynamodb_table.food_logs.name
      USER_PROFILES_TABLE   = aws_dynamodb_table.user_profiles.name
      SESSIONS_TABLE        = aws_dynamodb_table.sessions.name
      S3_BUCKET             = aws_s3_bucket.images.bucket
      OPENAI_MODEL          = "gpt-4o-mini"
      # DO NOT hardcode secrets here
	  OPENAI_API_KEY_PARAM   = "/telegram-food-bot/OPENAI_API_KEY"
      TELEGRAM_TOKEN_PARAM  = "/telegram-food-bot/TELEGRAM_BOT_TOKEN"
    }
  }


  tags = local.common_tags
}

resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${aws_lambda_function.bot.function_name}"
  retention_in_days = 14

  tags = local.common_tags
}

resource "aws_lambda_event_source_mapping" "sqs" {
  event_source_arn = aws_sqs_queue.bot.arn
  function_name    = aws_lambda_function.bot.arn
  batch_size       = 1
}
