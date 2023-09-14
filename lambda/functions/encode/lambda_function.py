import json
import subprocess
import logging
import os

import boto3


BUCKET_NAME = "lambda-encoder-bucket"

logger = logging.getLogger("chunk_encoder")
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
chunk_jobs = dynamodb.Table("chunk_jobs")
s3 = boto3.client("s3")


def response(status_code, body):
    return {"statusCode": status_code, "body": body}


def update_status(id_, status):
    chunk_jobs.update_item(
        Key={"id": id_},
        UpdateExpression="SET #s = :val",
        ExpressionAttributeNames={ "#s": "status" },
        ExpressionAttributeValues={ ":val": status }
    )


def encode_video(input_path, output_path):
    try:
        subprocess.run(
            [
                "/opt/ffmpeg",
                "-i", input_path,
                "-c:v", "libx264",
                "-b:v", "500k",
                output_path
            ],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg call failed with error: {e}")


def lambda_handler(event, context):
    logger.info(f"Received event: {event}, context: {context}")

    record = event["Records"][0]["dynamodb"]["NewImage"]
    id_ = record["id"]["S"]
    input_path = record["input_path"]["S"]
    output_path = record["output_path"]["S"]

    file_name = os.path.basename(input_path)
    local_input_path = f"/tmp/{file_name}"
    local_output_path = f"/tmp/encoded_{file_name}"

    update_status(id_, "encoding")
    s3.download_file(BUCKET_NAME, input_path, local_input_path)
    encode_video(local_input_path, local_output_path)
    s3.upload_file(local_output_path, BUCKET_NAME, output_path)
    update_status(id_, "encoded")

    return response(200, "OK")
