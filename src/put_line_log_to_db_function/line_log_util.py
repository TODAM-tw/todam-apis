import json
import logging
import re
import time
import uuid
from datetime import datetime

import boto3
from config import (
    IMAGE_EXTENSIONS,
    PARSE_IMAGE_FIFO_QUEUE_URL,
    PARSE_IMAGE_LAMBDA_FUNCTION_NAME,
    STICKERS_JSON_PATH,
    TODAM_TABLE_NAME,
)
from dynamodb_service import (
    get_registered_user,
    put_item_to_todam_table,
    query_todam_table,
)
from email_service import send_email
from sqs_service import send_message_to_sqs
from time_util import convert_timestamp_to_utc_plus_8
from user_service import apply_registration, get_user_type_by_id

# Initialize AWS clients
s3 = boto3.client("s3")
lambda_client = boto3.client("lambda")

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel("INFO")


def load_stickers():
    try:
        with open(STICKERS_JSON_PATH, "r") as f:
            stickers = json.load(f)
        return stickers
    except Exception as e:
        logger.error(f"Error loading stickers from {STICKERS_JSON_PATH}: {e}")
        raise


def handle_image_message(event, key):
    invoke_parse_image_lambda_payload = event
    time.sleep(2)
    lambda_client.invoke(
        FunctionName=PARSE_IMAGE_LAMBDA_FUNCTION_NAME,
        InvocationType="Event",
        Payload=json.dumps(invoke_parse_image_lambda_payload),
    )
    logger.info(f"Invoked Parse Image Lambda: {PARSE_IMAGE_LAMBDA_FUNCTION_NAME}")
    return {
        "statusCode": 200,
        "body": json.dumps(
            "This API ignored non-log file, but it will send to model to parse image"
        ),
    }


def process_line_log(data):
    message = data["events"][0]["message"]
    message_type = message.get("type")
    message_id = message.get("id")
    content = message.get("text", "")
    source = data["events"][0]["source"]
    group_id = source.get("groupId")
    user_id = source.get("userId")
    send_timestamp = data["events"][0].get("timestamp")

    random_uuid = str(uuid.uuid4()).replace("-", "")
    logger.info(f"Generated UUID: {random_uuid}")

    stickers = load_stickers()

    if message_type == "sticker":
        for sticker in stickers.get("start_recording", []):
            if (
                message.get("packageId") == sticker["packageId"]
                and message.get("stickerId") == sticker["stickerId"]
            ):
                content = "start recording"
                break
        for sticker in stickers.get("end_recording", []):
            if (
                message.get("packageId") == sticker["packageId"]
                and message.get("stickerId") == sticker["stickerId"]
            ):
                content = "end recording"
                break

    if message_type == "image":
        parse_image_message = {
            "dynamodb_table_name": TODAM_TABLE_NAME,
            "dynamodb_item_id": random_uuid,
        }
        send_message_to_sqs(PARSE_IMAGE_FIFO_QUEUE_URL, message=parse_image_message)

    item = {
        "id": random_uuid,
        "s3_object_key": data["s3_object_key"],
        "message_type": message_type,
        "message_id": message_id,
        "content": content,
        "group_id": group_id,
        "user_id": user_id,
        "user_type": get_user_type_by_id(user_id) if user_id else None,
        "send_timestamp": send_timestamp,
        "is_segment": False,
        "is_message": True,
    }
    put_item_to_todam_table(item)

    if content == "start recording":
        user_response = get_registered_user(user_id)
        if "Item" not in user_response or not user_response["Item"].get(
            "is_verified", False
        ):
            logger.info(
                "User is not registered or not verified, start recording failed."
            )
            return {
                "statusCode": 403,
                "body": json.dumps("User is not registered or not verified."),
            }

        response = query_todam_table(group_id)
        items = response.get("Items", [])

        if items:
            ongoing_segment = items[-1]
            segment_id = ongoing_segment["segment_id"]
            start_timestamp = convert_timestamp_to_utc_plus_8(
                int(ongoing_segment["start_timestamp"])
            )

            if "email" in user_response["Item"]:
                user_email = user_response["Item"]["email"]
                email_subject = "Recording Already Started"
                email_body = f"Hi, your group {group_id} is already recording.\nSegment ID: {segment_id}\nStart Time: {start_timestamp}"
                send_email(user_email, email_subject, email_body)

            return {
                "statusCode": 200,
                "body": json.dumps(
                    f"Group {group_id} is already recording. Segment ID: {segment_id}"
                ),
            }

        uuid_no_hyphen_for_segment = "".join(str(uuid.uuid4()).split("-"))
        logger.info(f"Generated UUID for segment: {uuid_no_hyphen_for_segment}")
        item = {
            "id": uuid_no_hyphen_for_segment,
            "s3_object_key": data["s3_object_key"],
            "segment_id": uuid_no_hyphen_for_segment,
            "start_timestamp": send_timestamp,
            "group_id": group_id,
            "message_id": message_id,
            "user_id": user_id,
            "send_timestamp": send_timestamp,
            "is_segment": True,
            "is_end": False,
        }
        put_item_to_todam_table(item)

        user_email = user_response["Item"]["email"]
        email_subject = "Recording Started"
        email_body = (
            f"Hi, the recording has started for your message in group {group_id}."
        )
        send_email(user_email, email_subject, email_body)

    if content == "end recording":
        user_response = get_registered_user(user_id)
        if "Item" not in user_response or not user_response["Item"].get(
            "is_verified", False
        ):
            logger.info("User is not registered or not verified, end recording failed.")
            return {
                "statusCode": 403,
                "body": json.dumps("User is not registered or not verified."),
            }

        response = query_todam_table(group_id)
        items = response.get("Items", [])
        if items:
            last_item = items[-1]
            last_item["end_timestamp"] = send_timestamp
            last_item["is_message"] = False
            last_item["is_end"] = True
            last_item["segment_name"] = (
                f"{convert_timestamp_to_utc_plus_8(int(last_item['start_timestamp']))}_{convert_timestamp_to_utc_plus_8(int(last_item['end_timestamp']))}"
            )
            put_item_to_todam_table(last_item)

            user_email = user_response["Item"]["email"]
            email_subject = "Recording Ended"
            start_time = convert_timestamp_to_utc_plus_8(
                int(last_item["start_timestamp"])
            )
            end_time = convert_timestamp_to_utc_plus_8(int(last_item["end_timestamp"]))
            email_body = (
                f"Hi, the recording has ended for your message in group {group_id}.\n"
                f"Segment ID: {last_item['segment_id']}\n"
                f"Start Time: {start_time}\n"
                f"End Time: {end_time}"
            )
            send_email(user_email, email_subject, email_body)

    registration_match = re.match(r"/register (\S+@ecloudvalley.com)", content)
    if registration_match:
        email = registration_match.group(1)
        apply_registration(user_id, email)

    return {
        "statusCode": 200,
        "body": json.dumps(item),
    }
