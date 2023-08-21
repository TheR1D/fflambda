import json
import subprocess
import logging


logger = logging.getLogger("lambda_encoder")
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    logger.info(f"Received event: {event}, context: {context}")
    # try:
    #     ffmpeg_version = subprocess.run(['/opt/ffmpeg', '-version'], capture_output=True, text=True, check=True)
    #     logger.info(f"ffmpeg version: {ffmpeg_version.stdout}")
    # except subprocess.CalledProcessError as e:
    #     logger.error(f"Command failed with error: {e}")
    # except FileNotFoundError:
    #     logger.error("ffmpeg is not installed or not found in /opt/ffmpeg.")
    #
    return {
        'statusCode': 200,
        'body': json.dumps(f"Hello from Lambda!")
    }
