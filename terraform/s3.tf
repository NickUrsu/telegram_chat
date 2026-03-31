resource "aws_s3_bucket" "images" {
  bucket = "${var.project_name}-images-${var.environment}-tokyo"

  lifecycle {
    prevent_destroy = true
  }

  tags = local.common_tags
}

resource "aws_s3_bucket_versioning" "images_versioning" {
  bucket = aws_s3_bucket.images.id

  versioning_configuration {
    status = "Enabled"
  }
}
