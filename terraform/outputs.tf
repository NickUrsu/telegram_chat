output "webhook_url" {
  description = "Telegram webhook URL"
  value       = "${aws_apigatewayv2_api.http_api.api_endpoint}/webhook"
}
