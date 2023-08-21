import argparse
import subprocess
import logging
import os
import sys

logger = logging.getLogger("lambda_encoder")
FFMPEG_PATH = "/opt/ffmpeg"


def check_ffmpeg_exists():
    try:
        output = subprocess.run([FFMPEG_PATH, "-version"], capture_output=True, text=True, check=True)
        logger.info(f"ffmpeg version: {output}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg command failed with error: {e}")
        return False
    except FileNotFoundError:
        logger.error(f"ffmpeg is not installed or not found in {FFMPEG_PATH}")
        return False


def run_ffmpeg(video_path, segment_time, output_path):
    cmd = [
        FFMPEG_PATH,
        "-i", video_path,
        "-c", "copy",
        "-map", "0",
        "-segment_time", str(segment_time),
        "-f", "segment",
        "-reset_timestamps", "1",
        f"{output_path}/%04d.mp4"
    ]
    subprocess.run(cmd)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Segment a video using ffmpeg.")
    parser.add_argument("video_path", help="Path to the input video.")
    parser.add_argument("segment_time", help="Duration of each segment in seconds 00:00:01.")
    parser.add_argument("output_path", help="Path to store the segmented videos.")
    
    args = parser.parse_args()

    # Check if ffmpeg is installed and accessible
    if not check_ffmpeg_exists():
        exit(1)

    # Check if video_path exists
    if not os.path.exists(args.video_path):
        logger.error(f"Video file {args.video_path} does not exist.\n")
        exit(1)

    # Create output_path folder if it doesn't exist
    if not os.path.exists(args.output_path):
        os.makedirs(args.output_path)

    run_ffmpeg(args.video_path, args.segment_time, args.output_path)

