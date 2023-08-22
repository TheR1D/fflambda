import json
import subprocess
import logging
import os
import uuid

import boto3


SEGMENT_TIME = "00:00:06"
BUCKET_NAME = "lambda-encoder-bucket"
INGEST_FOLDER = "input"

logger = logging.getLogger("lambda_encoder")
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
ingest_jobs = dynamodb.Table("ingest_jobs")
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


def update_status(id_, file_name, status):
    ingest_jobs.update_item(
        Key={"id": id_, "file_name": file_name},
        UpdateExpression="SET #s = :val",
        ExpressionAttributeNames={ "#s": "status" },
        ExpressionAttributeValues={ ":val": status }
    )


def create_encoding_job(ingest_job, input_path, output_path):
    chunk_jobs.put_item(
       Item={
            "id": str(uuid.uuid4()),
            "ingest_job": ingest_job,
            "input_path": input_path,
            "output_path": output_path,
            "status": "new",
        }
    )


def lambda_handler(event, context):
    logger.info(f"Received event: {event}, context: {context}")
    record = event["Records"][0]["dynamodb"]["NewImage"]
    if record["status"]["S"] != "new":
        return response(400, "Record status must be \"new\"")

    id_ = record["id"]["S"]
    file_name = record["file_name"]["S"]
    s3_key = f"{INGEST_FOLDER}/{file_name}"
    local_path = f"/tmp/{file_name}"
    output_folder = "/tmp/output_chunks"
    os.makedirs(output_folder, exist_ok=True)
    name_no_extension = os.path.splitext(file_name)[0]

    update_status(id_, file_name, "ingesting")

    # Download mezanine from S3 bucket.
    s3.download_file(BUCKET_NAME, s3_key, local_path)
    
    # Split video into multiple chunks using ffmpeg.
    success = chunk_video(local_path, output_folder, file_name)

    # Upload chunks to S3 and create encoding jobs.
    for file in [file for file in os.listdir(output_folder)]:
        local_file_path = os.path.join(output_folder, file)
        s3_output_path = f"output/{name_no_extension}/{file}"
        s3_output_path_encoded = f"output/{name_no_extension}/encoded_{file}"
        s3.upload_file(local_file_path, BUCKET_NAME, s3_output_path)
        create_encoding_job(id_, s3_output_path, s3_output_path_encoded)

    update_status(id_, file_name, "encoding")
    
    return response(200, "OK")
