import json
import logging
from pathlib import Path

import boto3
from config import IMAGE_EXTENSIONS, S3_BUCKET
from line_log_util import handle_image_message, process_line_log

s3 = boto3.client("s3")

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel("INFO")


def lambda_handler(event, context):
    logger.info("Triggered by S3 Put event")
    logger.info("Event: %s", event)

    key = event["Records"][0]["s3"]["object"]["key"]
    path = Path(key)
    file_extension = path.suffix.lower()
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)

    if file_extension in IMAGE_EXTENSIONS:
        return handle_image_message(event, key)

    data = json.loads(obj["Body"].read().decode("utf-8"))
    data["s3_object_key"] = key  # Add s3_object_key to data
    return process_line_log(data)
