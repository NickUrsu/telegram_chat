resource "aws_sqs_queue" "bot_dlq" {
  name                      = "${var.project_name}-dlq"
  message_retention_seconds = 86400  # 1 day
}

resource "aws_sqs_queue" "bot" {
  name                       = "${var.project_name}-queue"
  visibility_timeout_seconds = 70    # > Lambda timeout (60s)
  message_retention_seconds  = 3600  # 1 hour

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.bot_dlq.arn
    maxReceiveCount     = 3
  })
}
