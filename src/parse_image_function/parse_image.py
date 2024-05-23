import json
import logging
import os
from pathlib import Path

import boto3
import requests
from botocore.exceptions import BotoCoreError, ClientError

logging.basicConfig(level=logging.INFO)
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
        print("============ Call API - parse image ===========")
        print(f"Payload: {payload}")
        print("==================================")
        response = requests.post(parse_image_api_url, json=payload)
        response.raise_for_status()
        # Return a structured dictionary that can be easily used or serialized
        return {
            "statusCode": response.status_code,
            "body": response.json(),  # safely assuming the response is in JSON format
        }
    except requests.RequestException as e:
        # Handle exceptions by returning a standardized error response
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
        return response
    except (ClientError, BotoCoreError) as e:
        raise Exception(f"Error receiving message from SQS: {e}")


def lambda_handler(event, context):
    print("==================================")
    print("Parse Image FIFO SQS URL: " + parse_image_fifo_queue_url)
    print("==================================")
    key = event["Records"][0]["s3"]["object"]["key"]
    path = Path(key)
    file_extension = path.suffix.lower()

    if file_extension not in IMAGE_EXTENSIONS:
        return {"statusCode": 400, "body": json.dumps("Unsupported file type")}

    print("============ Receive message from SQS ===========")
    response = receive_message_from_sqs(parse_image_fifo_queue_url)
    messages = response.get("Messages", [])
    message_id = messages[0]["MessageId"]
    print(f"Received {len(messages)} messages from SQS")
    print(f"Message ID: {message_id}")
    print("==================================")
    if not messages:
        return {"statusCode": 200, "body": json.dumps("No messages to process")}

    print("============ Process message ===========")
    message = messages[0]
    body = json.loads(message["Body"])
    receipt_handle = message["ReceiptHandle"]

    print(f"Message Body: {body}")
    print("==================================")
    payload = {
        "s3_bucket_name": bucket,
        "s3_object_key": key,
        "dynamodb_table_name": todam_table_name,
        "dynamodb_item_id": body.get("dynamodb_item_id"),
    }

    result = api_parse_image(payload)
    print("============ Call API - parse image ===========")
    print(f"API response: {result}")
    print("==================================")
    if result["statusCode"] == 200:
        sendMessageResult = (
            result["body"].get("SendMessageResponse", {}).get("SendMessageResult", {})
        )
        if sendMessageResult.get("MessageId") is not None:
            print("============ Delete message from SQS ===========")
            sqs.delete_message(
                QueueUrl=parse_image_fifo_queue_url, ReceiptHandle=receipt_handle
            )
            print("Message deleted from SQS")
            print("==================================")
            return {
                "statusCode": 200,
                "body": json.dumps("Image parsing request sent successfully"),
            }

    return {
        "statusCode": result.get("statusCode", 500),
        "body": json.dumps("Failed to parse image or invalid response"),
    }
