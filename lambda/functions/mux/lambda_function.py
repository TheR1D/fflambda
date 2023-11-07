import json
import subprocess
import logging
import os

import boto3


BUCKET_NAME = "lambda-encoder-bucket"

logger = logging.getLogger("mux_encoder")
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
chunk_jobs = dynamodb.Table("chunk_jobs")
s3 = boto3.client("s3")


def response(status_code, body):
    return {"statusCode": status_code, "body": body}

def get_chunks(video_id):
    result = chunk_jobs.query(
        IndexName="video_id-index",
        KeyConditionExpression=boto3.dynamodb.conditions.Key('video_id').eq(video_id)
    )
    return result.get("Items", [])


def create_chunk_list(input_folder):
    chunk_list = []
    files_list = os.listdir(input_folder)
    files_list.sort()

    for file_name in files_list:
        if file_name.endswith(".mp4"):
            chunk_list.append(f"file '{file_name}'")

    list_file = f"{input_folder}/chunk_list.txt"
    with open(list_file, "w") as f:
        f.write("\n".join(chunk_list))

    return list_file


def mux_chunks(list_file_path, audio_file_path, output_file_path):
    try:
        subprocess.run(
            [
                "/opt/ffmpeg",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file_path,
                "-i", audio_file_path,
                "-c", "copy",
                output_file_path
            ],
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg mux call failed with error: {e}")


def lambda_handler(event, context):
    logger.info(f"Received event: {event}, context: {context}")
    video_id = event.get("video_id")
    if not video_id:
        return response(400, "Missing video_id")

    local_output_dir = f"/tmp/{video_id}"
    os.makedirs(local_output_dir, exist_ok=True)
    audio_downloaded = False

    for chunk in get_chunks(video_id):
        output_path = chunk["output_path"]
        output_dir = os.path.dirname(output_path)
        file_name = os.path.basename(output_path)
        local_output_path = f"{local_output_dir}/{file_name}"

        audio_output_path = f"{output_dir}/audio.aac"
        audio_output_local_path = f"{local_output_dir}/audio.aac"

        if not audio_downloaded:
            s3.download_file(BUCKET_NAME, audio_output_path, audio_output_local_path)
            audio_downloaded = True
        s3.download_file(BUCKET_NAME, output_path, local_output_path)

    list_file_path = create_chunk_list(local_output_dir)
    audio_file_path = f"{local_output_dir}/audio.aac"
    output_file_path = f"/tmp/{video_id}.mp4"

    mux_chunks(list_file_path, audio_file_path, output_file_path)

    output_s3_path = f"encoded/mux_{video_id}.mp4"
    s3.upload_file(output_file_path, BUCKET_NAME, output_s3_path)

    return response(200, "OK")
