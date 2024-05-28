import json
import logging
import os
from pathlib import Path

import boto3
import requests
from botocore.exceptions import BotoCoreError, ClientError

# Set up logger
logger = logging.getLogger()
logger.setLevel("INFO")


s3 = boto3.client("s3")
bucket = os.environ["S3_BUCKET"]
sqs = boto3.client("sqs")
todam_table_name = os.environ.get("TODAM_TABLE", "todam_table")
parse_image_fifo_queue_url = os.environ["PARSE_IMAGE_FIFO_QUEUE_URL"]
parse_image_api_url = os.environ["PARSE_IMAGE_API_URL"]

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"}


def api_parse_image(payload: dict):
    """Send a POST request to parse an image."""
    try:
        logger.info("============ Call API - parse image ===========")
        logger.info("Payload: %s", payload)
        response = requests.post(parse_image_api_url, json=payload)
        response.raise_for_status()
        return {
            "statusCode": response.status_code,
            "body": response.json(),  # safely assuming the response is in JSON format
        }
    except requests.RequestException as e:
        logger.error("Error calling API: %s", e)
        if hasattr(e, "response") and e.response:
            return {"statusCode": e.response.status_code, "body": str(e)}
        else:
            return {"statusCode": 500, "body": str(e)}


def receive_message_from_sqs(queue_url: str) -> dict:
    try:
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            VisibilityTimeout=30,
            WaitTimeSeconds=5,
        )
        logger.info("Received message from SQS: %s", response)
        return response
    except (ClientError, BotoCoreError) as e:
        logger.error("Error receiving message from SQS: %s", e)
        raise Exception(f"Error receiving message from SQS: {e}")


def lambda_handler(event, context):
    logger.info("Lambda function started")
    logger.info("Parse Image FIFO SQS URL: %s", parse_image_fifo_queue_url)

    key = event["Records"][0]["s3"]["object"]["key"]
    path = Path(key)
    file_extension = path.suffix.lower()

    if file_extension not in IMAGE_EXTENSIONS:
        logger.error("Unsupported file type: %s", file_extension)
        return {"statusCode": 400, "body": json.dumps("Unsupported file type")}

    logger.info("============ Receive message from SQS ===========")
    response = receive_message_from_sqs(parse_image_fifo_queue_url)
    messages = response.get("Messages", [])

    if not messages:
        logger.info("No messages to process")
        return {"statusCode": 200, "body": json.dumps("No messages to process")}

    message = messages[0]
    message_id = message["MessageId"]
    receipt_handle = message["ReceiptHandle"]
    body = json.loads(message["Body"])

    logger.info("Received %d messages from SQS", len(messages))
    logger.info("Message ID: %s", message_id)
    logger.info("Message Body: %s", body)

    payload = {
        "s3_bucket_name": bucket,
        "s3_object_key": key,
        "dynamodb_table_name": todam_table_name,
        "dynamodb_item_id": body.get("dynamodb_item_id"),
    }

    result = api_parse_image(payload)
    logger.info("============ Call API - parse image ===========")
    logger.info("API response: %s", result)

    if result["statusCode"] == 200:
        sendMessageResult = (
            result["body"].get("SendMessageResponse", {}).get("SendMessageResult", {})
        )
        if sendMessageResult.get("MessageId") is not None:
            logger.info("============ Delete message from SQS ===========")
            sqs.delete_message(
                QueueUrl=parse_image_fifo_queue_url, ReceiptHandle=receipt_handle
            )
            logger.info("Message deleted from SQS")
            return {
                "statusCode": 200,
                "body": json.dumps("Image parsing request sent successfully"),
            }

    logger.error("Failed to parse image or invalid response")
    return {
        "statusCode": result.get("statusCode", 500),
        "body": json.dumps("Failed to parse image or invalid response"),
    }
