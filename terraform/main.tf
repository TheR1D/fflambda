provider "aws" {
  region = "eu-west-1"
}

# Create chunking jobs table for output chunks.
resource "aws_dynamodb_table" "chunk_jobs" {
  name = "chunk_jobs"
  billing_mode = "PAY_PER_REQUEST"
  stream_enabled = true
  stream_view_type = "NEW_IMAGE"
  hash_key = "id"

  attribute {
    name = "id"
    type = "S"
  }
}

# Create S3 bucket for input video files.
resource "aws_s3_bucket" "ingestor_bucket" {
  bucket = "lambda-ingestor-bucket"
}

resource "aws_lambda_permission" "allow_s3_lambda_execution" {
  statement_id  = "AllowExecutionFromS3IngestorBucket"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest_encoder.arn
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.ingestor_bucket.arn
}

# Create S3 bucket for chunks and output video files.
resource "aws_s3_bucket" "encoder_bucket" {
  bucket = "lambda-encoder-bucket"
}

resource "aws_iam_policy" "s3_encoder_crud_access_policy" {
  name = "s3_encoder_crud_access_policy"
  description = "S3 CRUD actions"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = [
          "s3:ListBucket",
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ],
        Effect = "Allow",
        Resource = [
          aws_s3_bucket.encoder_bucket.arn,
          "${aws_s3_bucket.encoder_bucket.arn}/*",
          aws_s3_bucket.ingestor_bucket.arn,
          "${aws_s3_bucket.ingestor_bucket.arn}/*",
        ]
      }
    ]
  })
}

# Lambda layer source files.
data "archive_file" "lambda_encoding_layer_archive" {
  type = "zip"
  source_dir = "../lambda/layers/encoding/"
  output_path = "lambda_encoding_layer_payload.zip"
}

# Create lambda layer with tools required like ffmpeg.
resource "aws_lambda_layer_version" "lambda_encoding_layer" {
  layer_name = "lambda_encoding_layer"
  filename = "lambda_encoding_layer_payload.zip"

  compatible_runtimes = ["python3.10"]
}

# Create access role for lambda.
resource "aws_iam_role" "lambda_role" {
  name = "lambda_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Action = "sts:AssumeRole",
        Principal = {
          Service = "lambda.amazonaws.com"
        },
        Effect = "Allow",
        Sid = ""
      }
    ]
  })
}

# Ingest encoder lambda function source code.
data "archive_file" "ingest_lambda_source" {
  type = "zip"
  source_file = "../lambda/functions/ingest/lambda_function.py"
  output_path = "ingest_lambda_payload.zip"
}

# Create lambda function to process new inserts in to ingest_jobs.
resource "aws_lambda_function" "ingest_encoder" {
  function_name = "ingest_encoder"
  handler = "lambda_function.lambda_handler"
  runtime = "python3.10"
  filename = "ingest_lambda_payload.zip"
  timeout = 500
  memory_size = 1024
  architectures = ["arm64"]
  source_code_hash = data.archive_file.ingest_lambda_source.output_base64sha256
  role = aws_iam_role.lambda_role.arn

  layers = [
    aws_lambda_layer_version.lambda_encoding_layer.arn
  ]

  ephemeral_storage {
    size = 1024
  }
}

# Chunk encoder lambda function source code.
data "archive_file" "chunk_lambda_source" {
  type = "zip"
  source_file = "../lambda/functions/encode/lambda_function.py"
  output_path = "chunk_lambda_payload.zip"
}

# Create lambda function to process new inserts in to chunk_jobs.
resource "aws_lambda_function" "chunk_encoder" {
  function_name = "chunk_encoder"
  handler = "lambda_function.lambda_handler"
  runtime = "python3.10"
  filename = "chunk_lambda_payload.zip"
  timeout = 500
  memory_size = 3008
  architectures = ["arm64"]
  source_code_hash = data.archive_file.chunk_lambda_source.output_base64sha256
  role = aws_iam_role.lambda_role.arn

  layers = [
    aws_lambda_layer_version.lambda_encoding_layer.arn
  ]

  ephemeral_storage {
    size = 512
  }
}

# Add DB full access arn to lambda role.
resource "aws_iam_role_policy_attachment" "policy_lambda_dynamodb" {
  role = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
}

# Attach ingest lambda function as a trigger to ingest s3 bucket.
resource "aws_s3_bucket_notification" "s3_ingest_event" {
  bucket = aws_s3_bucket.ingestor_bucket.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.ingest_encoder.arn
    events = ["s3:ObjectCreated:*"]
    filter_suffix = ".mp4"
  }

  depends_on = [aws_lambda_permission.allow_s3_lambda_execution]
}

# Attach chunk lambda function as a trigger to DynamoDB.
resource "aws_lambda_event_source_mapping" "trigger_chunk_encoder" {
  event_source_arn = aws_dynamodb_table.chunk_jobs.stream_arn
  function_name = aws_lambda_function.chunk_encoder.function_name
  batch_size = 1
  parallelization_factor = 10
  starting_position = "LATEST"

  filter_criteria {
    filter {
      pattern = jsonencode({eventName = ["INSERT"]})
    }
  }
}

# IAM policy for Lambda to write to CloudWatch Logs
resource "aws_iam_policy" "lambda_cloudwatch_logs" {
  name = "LambdaCloudWatchLogsPolicy"
  description = "Allows Lambda function to write logs to CloudWatch"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ],
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Attach the CloudWatch logs policy to the Lambda execution role
resource "aws_iam_role_policy_attachment" "lambda_logs_attach" {
  policy_arn = aws_iam_policy.lambda_cloudwatch_logs.arn
  role = aws_iam_role.lambda_role.name
}

# Attach the S3 CRUD policy to the Lambda execution role.
resource "aws_iam_role_policy_attachment" "lambda_s3_attach" {
  policy_arn = aws_iam_policy.s3_encoder_crud_access_policy.arn
  role = aws_iam_role.lambda_role.name
}
