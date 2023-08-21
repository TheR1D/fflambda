import json
import subprocess
import logging
import os

import boto3


logger = logging.getLogger("lambda_encoder")
logger.setLevel(logging.INFO)

SEGMENT_TIME = "00:00:06"
BUCKET_NAME = "lambda-encoder-bucket"
INGEST_FOLDER = "input"


def response(status_code, body):
    return {"statusCode": status_code, "body": body}


def convert_video(input_path, output_folder, file_name):
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


def lambda_handler(event, context):
    logger.info(f"Received event: {event}, context: {context}")
    record = event["Records"][0]["dynamodb"]["NewImage"]
    if record["status"]["S"] != "new":
        return response(400, "Record status must be \"new\"")

    file_name = record["file_name"]["S"]
    s3_key = f"{INGEST_FOLDER}/{file_name}"
    local_path = f"/tmp/{file_name}"
    output_folder = "/tmp/output_chunks"
    os.makedirs(output_folder, exist_ok=True)
    name_no_extension = os.path.splitext(file_name)[0]

    s3 = boto3.client('s3')
    s3.download_file(BUCKET_NAME, s3_key, local_path)
    
    success = convert_video(local_path, output_folder, file_name)

    for file in [file for file in os.listdir(output_folder)]:
        local_file_path = os.path.join(output_folder, file)
        s3_output_path = f"output/{name_no_extension}/{file}"
        s3.upload_file(local_file_path, BUCKET_NAME, s3_output_path)

    return response(200, "OK")
