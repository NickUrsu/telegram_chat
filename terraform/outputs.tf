output "webhook_url" {
  description = "Telegram webhook URL"
  value       = "${aws_api_gateway_stage.prod.invoke_url}/webhook"
}
