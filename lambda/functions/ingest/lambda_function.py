import json
import subprocess
import logging
import os
import uuid
import urllib

import boto3


SEGMENT_TIME = "00:00:06"

logger = logging.getLogger("lambda_encoder")
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
chunk_jobs = dynamodb.Table("chunk_jobs")


def response(status_code, body):
    return {"statusCode": status_code, "body": body}


def chunk_video(input_path, output_folder, file_name):
    output_path = f"{output_folder}/%04d_{file_name}"
    try:
        subprocess.run(
            [
                "/opt/ffmpeg",
                "-i", input_path,
                "-c", "copy",
                "-map", "0",
                "-segment_time", SEGMENT_TIME,
                "-f", "segment",
                "-reset_timestamps", "1",
                output_path
            ],
            capture_output=True,
            text=True,
            check=True
        )
        # os.system(f"python /opt/chunk.py {input_path} {SEGMENT_TIME} {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg call failed with error: {e}")
        return False


def create_encoding_job(input_path, output_path):
    chunk_jobs.put_item(
       Item={
            "id": str(uuid.uuid4()),
            "input_path": input_path,
            "output_path": output_path,
            "status": "new",
        }
    )


def lambda_handler(event, context):
    logger.info(f"Received event: {event}, context: {context}")
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    s3_key = urllib.parse.unquote_plus(
        event["Records"][0]["s3"]["object"]["key"], encoding="utf-8"
    )
    file_name = os.path.basename(s3_key)
    local_path = f"/tmp/{file_name}"
    output_folder = "/tmp/output_chunks"
    os.makedirs(output_folder, exist_ok=True)
    name_no_extension = os.path.splitext(file_name)[0]

    # Download mezanine from S3 bucket.
    s3.download_file(bucket, s3_key, local_path)
    # Split video into multiple chunks using ffmpeg.
    success = chunk_video(local_path, output_folder, file_name)

    # Upload chunks to S3 and create encoding jobs.
    for file in [file for file in os.listdir(output_folder)]:
        local_file_path = os.path.join(output_folder, file)
        output_bucket = "lambda-encoder-bucket"
        s3_output_path = f"{name_no_extension}/{file}"
        s3_output_path_encoded = f"{name_no_extension}/encoded_{file}"
        s3.upload_file(local_file_path, output_bucket, s3_output_path)
        create_encoding_job(s3_output_path, s3_output_path_encoded)

    return response(200, "OK")
