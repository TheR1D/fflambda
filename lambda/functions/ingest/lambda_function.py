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


def extract_audio(input_path, output_path):
    try:
        subprocess.run(
            [
                "/opt/ffmpeg",
                "-i", input_path,
                "-vn",
                "-acodec", "copy",
                output_path
            ],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg audio extract call failed with error: {e}")

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
                "-an",
                output_path
            ],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg chunk call failed with error: {e}")


def create_encoding_job(input_path, output_path, video_id):
    chunk_jobs.put_item(
       Item={
            "id": str(uuid.uuid4()),
            "video_id": video_id,
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
    audio_output_path = "/tmp/audio.aac"
    os.makedirs(output_folder, exist_ok=True)
    name_no_extension = os.path.splitext(file_name)[0]
    output_bucket = "lambda-encoder-bucket"
    video_id = str(uuid.uuid4())

    # Download mezanine from S3 bucket.
    s3.download_file(bucket, s3_key, local_path)
    # Extract audio from video.
    extract_audio(local_path, audio_output_path)
    # Split video into multiple chunks using ffmpeg.
    chunk_video(local_path, output_folder, file_name)

    # Upload audio to S3.
    s3.upload_file(audio_output_path, output_bucket, f"{name_no_extension}/audio.aac")

    # Upload chunks to S3 and create encoding jobs.
    for file in [file for file in os.listdir(output_folder)]:
        local_file_path = os.path.join(output_folder, file)
        s3_output_path = f"{name_no_extension}/{file}"
        s3_output_path_encoded = f"{name_no_extension}/encoded_{file}"
        s3.upload_file(local_file_path, output_bucket, s3_output_path)
        create_encoding_job(s3_output_path, s3_output_path_encoded, video_id)

    return response(200, "OK")
