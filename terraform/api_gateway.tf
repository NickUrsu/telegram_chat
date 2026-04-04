resource "aws_api_gateway_rest_api" "bot" {
  name = "${var.project_name}-api"
}

resource "aws_api_gateway_resource" "webhook" {
  rest_api_id = aws_api_gateway_rest_api.bot.id
  parent_id   = aws_api_gateway_rest_api.bot.root_resource_id
  path_part   = "webhook"
}

resource "aws_api_gateway_method" "post" {
  rest_api_id   = aws_api_gateway_rest_api.bot.id
  resource_id   = aws_api_gateway_resource.webhook.id
  http_method   = "POST"
  authorization = "NONE"
}

data "aws_caller_identity" "current" {}

# Direct SQS integration
resource "aws_api_gateway_integration" "sqs" {
  rest_api_id             = aws_api_gateway_rest_api.bot.id
  resource_id             = aws_api_gateway_resource.webhook.id
  http_method             = "POST"
  type                    = "AWS"
  integration_http_method = "POST"
  uri                     = "arn:aws:apigateway:${var.region}:sqs:path/${data.aws_caller_identity.current.account_id}/${aws_sqs_queue.bot.name}"
  credentials             = aws_iam_role.apigw_sqs_role.arn

  request_parameters = {
    "integration.request.header.Content-Type" = "'application/x-www-form-urlencoded'"
  }

  request_templates = {
    "application/json" = "Action=SendMessage&MessageBody=$util.urlEncode($input.body)"
  }
}

# Return 200 to Telegram immediately
resource "aws_api_gateway_method_response" "ok" {
  rest_api_id = aws_api_gateway_rest_api.bot.id
  resource_id = aws_api_gateway_resource.webhook.id
  http_method = aws_api_gateway_method.post.http_method
  status_code = "200"
}

resource "aws_api_gateway_integration_response" "ok" {
  rest_api_id = aws_api_gateway_rest_api.bot.id
  resource_id = aws_api_gateway_resource.webhook.id
  http_method = aws_api_gateway_method.post.http_method
  status_code = aws_api_gateway_method_response.ok.status_code

  depends_on = [
    aws_api_gateway_integration.sqs
  ]
}

resource "aws_api_gateway_deployment" "prod" {
  rest_api_id = aws_api_gateway_rest_api.bot.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.webhook.id,
      aws_api_gateway_method.post.id,
      aws_api_gateway_integration.sqs.id,
      aws_api_gateway_method_response.ok.id,
      aws_api_gateway_integration_response.ok.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on  = [aws_api_gateway_integration.sqs]
}

resource "aws_api_gateway_stage" "prod" {
  rest_api_id   = aws_api_gateway_rest_api.bot.id
  deployment_id = aws_api_gateway_deployment.prod.id
  stage_name    = "prod"
}
