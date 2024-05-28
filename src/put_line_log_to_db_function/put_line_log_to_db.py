import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import boto3
from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError
from time_util import convert_timestamp_to_utc_plus_8

s3 = boto3.client("s3")
ses_client = boto3.client("ses")
dynamodb = boto3.resource("dynamodb")
todam_table_name = os.environ.get("TODAM_TABLE", "todam_table")
todam_table = dynamodb.Table(todam_table_name)
registered_user_table = dynamodb.Table("registered_user_table")
verify_registration_api_url = f"https://{os.environ.get('VERIFY_REGISTRATION_API_URL')}.execute-api.us-east-1.amazonaws.com/dev/verify-registration"
sqs = boto3.client("sqs")
parse_image_fifo_queue_url = os.environ["PARSE_IMAGE_FIFO_QUEUE_URL"]
lambda_client = boto3.client("lambda")
STICKERS_JSON_PATH = "stickers.json"

parse_image_lambda_function_name = os.environ["PARSE_IMAGE_LAMBDA_FUNCTION_NAME"]

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"}

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_stickers():
    try:
        with open(STICKERS_JSON_PATH, "r") as f:
            stickers = json.load(f)
        return stickers
    except Exception as e:
        logger.error(f"Error loading stickers from {STICKERS_JSON_PATH}: {e}")
        raise


def send_message_to_sqs(
    message: dict, message_group_id: str = "default_message_group_id"
) -> dict:
    try:
        response = sqs.send_message(
            QueueUrl=parse_image_fifo_queue_url,
            MessageBody=json.dumps(message),
            MessageGroupId=message_group_id,
        )
        print(f"Message sent successfully. MessageId: {response['MessageId']}")
        return response
    except ClientError as e:
        print(f"Error sending message to SQS: {e.response['Error']['Message']}")
        raise e
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise e


def apply_registration(user_id: str, email: str) -> None:
    # Get the current item to check if already registered or recent attempt
    response = registered_user_table.get_item(Key={"user_id": user_id})
    if "Item" in response:
        if response["Item"].get("is_verified"):
            print("You have already registered.")
            return  # User is already verified, no need to proceed

        # Check if an attempt was made less than a minute ago
        current_time_millis = int(datetime.now(timezone.utc).timestamp() * 1000)
        if (
            current_time_millis - response["Item"]["apply_timestamp"] < 60 * 1000
        ):  # 1 minute in milliseconds
            print("Please wait a moment before requesting a new verification email.")
            return  # Too soon to resend verification email

    # Construct the registration link
    random_code = str(uuid.uuid4())
    registration_url = (
        verify_registration_api_url + f"?user_id={user_id}&code={random_code}"
    )

    # Email content
    email_body = f"Hi {email.split('@')[0]}, Please click on the link to complete your registration:\n {registration_url}"
    email_subject = "Todam - Complete Your Registration"

    # Create a new user item in registered_user_table
    current_time = datetime.now(timezone.utc)
    unix_timestamp_millis = int(current_time.timestamp() * 1000)
    item = {
        "user_id": user_id,
        "email": email,
        "name": email.split("@")[0],
        "apply_timestamp": unix_timestamp_millis,
        "verification_code": random_code,
        "is_verified": False,
    }
    registered_user_table.put_item(Item=item)
    print(f"User {email} has applied for registration")

    # Sending the registration email
    ses_client.send_email(
        Source="TODAM <ptqwe20020413@gmail.com>",
        Destination={"ToAddresses": [email]},
        Message={
            "Subject": {"Data": email_subject},
            "Body": {"Text": {"Data": email_body}},
        },
    )
    print(f"Email sent to {email}")


def get_user_type_by_id(user_id: str) -> str:
    response = registered_user_table.get_item(Key={"user_id": user_id})

    # Check if the user item exists
    item = response.get("Item")
    if not item:
        return "Client"

    # Check if user is verified
    is_verified = item.get("is_verified", False)
    if is_verified:
        return "TAM"
    else:
        return "Client"


def lambda_handler(event, context):
    print("=====================================")
    print("Triggered by S3 Put event")
    print("Event:", event)
    print("=====================================")

    bucket = os.environ["S3_BUCKET"]
    key = event["Records"][0]["s3"]["object"]["key"]
    path = Path(key)
    file_extension = path.suffix.lower()
    obj = s3.get_object(Bucket=bucket, Key=key)

    # Check object key ends with .log
    if file_extension in IMAGE_EXTENSIONS:
        invoke_parse_image_lambda_paylod = event

        time.sleep(2)

        lambda_client.invoke(
            FunctionName=parse_image_lambda_function_name,
            InvocationType="Event",
            Payload=json.dumps(invoke_parse_image_lambda_paylod),
        )
        print("=====================================")
        print(f"Get object from S3, object key: {key}")
        print("It is an image file. Send to Parse Image Lambda.")
        print(f"Invoke Parse Image Lambda: {parse_image_lambda_function_name}")
        print("=====================================")
        return {
            "statusCode": 200,
            "body": json.dumps(
                "This API Ignored non-log file. but it will send to model to parse image"
            ),
        }

    data = obj["Body"].read().decode("utf-8")
    data = json.loads(data)

    print("Lines:")
    print(data)

    # Extract data
    message = data["events"][0]["message"]
    message_type = message.get("type")
    message_id = message.get("id")
    content = message.get("text", "")
    source = data["events"][0]["source"]
    group_id = source.get("groupId")
    user_id = source.get("userId")
    send_timestamp = data["events"][0].get("timestamp")

    # Generate UUID
    random_uuid = str(uuid.uuid4())
    uuid_no_hyphen = "".join(random_uuid.split("-"))
    print(f"Generated UUID: {uuid_no_hyphen}")

    # Check if the message is a sticker
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

    # If the message_type is image, send it to the image parsing service
    if message_type == "image":
        parse_image_message = {
            "dynamodb_table_name": todam_table_name,
            "dynamodb_item_id": uuid_no_hyphen,
        }
        send_message_to_sqs(message=parse_image_message)

    # Put data to DynamoDB
    item = {
        "id": uuid_no_hyphen,
        "s3_object_key": key,
        "message_type": message_type,
        "message_id": message_id,
        "content": content,
        "group_id": group_id,
        "user_id": user_id,
        "user_type": (get_user_type_by_id(user_id) if user_id else None),
        "send_timestamp": send_timestamp,
        "is_segment": False,
        "is_message": True,
    }

    todam_table.put_item(Item=item)

    if content == "start recording":
        # Check if the user is registered and verified
        user_response = registered_user_table.get_item(Key={"user_id": user_id})
        if "Item" not in user_response or not user_response["Item"].get(
            "is_verified", False
        ):
            print("User is not registered or not verified, start recording failed.")
            return {
                "statusCode": 403,
                "body": json.dumps("User is not registered or not verified."),
            }

        # Check if there is an ongoing recording
        response = todam_table.query(
            IndexName="GroupTimeIndex",
            KeyConditionExpression=boto3.dynamodb.conditions.Key("group_id").eq(
                group_id
            ),
            FilterExpression=Attr("is_segment").eq(True) & Attr("is_end").eq(False),
        )
        items = response.get("Items", [])

        if items:
            # Send an email to the user about the ongoing recording
            ongoing_segment = items[-1]
            segment_id = ongoing_segment["segment_id"]
            start_timestamp = convert_timestamp_to_utc_plus_8(
                int(ongoing_segment["start_timestamp"])
            )

            # Get the user's email address
            if "email" in user_response["Item"]:
                user_email = user_response["Item"]["email"]
                email_subject = "Recording Already Started"
                email_body = f"Hi, your group {group_id} is already recording.\nSegment ID: {segment_id}\nStart Time: {start_timestamp}"

                try:
                    ses_client.send_email(
                        Source="TODAM <ptqwe20020413@gmail.com>",
                        Destination={"ToAddresses": [user_email]},
                        Message={
                            "Subject": {"Data": email_subject},
                            "Body": {"Text": {"Data": email_body}},
                        },
                    )
                    print(f"Email sent to {user_email} about ongoing recording")
                except ClientError as e:
                    print(f"Error sending email: {e.response['Error']['Message']}")
                except Exception as e:
                    print(f"An unexpected error occurred: {e}")

            return {
                "statusCode": 200,
                "body": json.dumps(
                    f"Group {group_id} is already recording. Segment ID: {segment_id}"
                ),
            }

        # Start a new recording segment
        uuid_no_hyphen_for_segment = "".join(str(uuid.uuid4()).split("-"))
        print(f"Generated UUID for segment: {uuid_no_hyphen_for_segment}")
        item = {
            "id": uuid_no_hyphen_for_segment,
            "s3_object_key": key,
            "segment_id": uuid_no_hyphen_for_segment,
            "start_timestamp": send_timestamp,
            "group_id": group_id,
            "message_id": message_id,
            "user_id": user_id,
            "send_timestamp": send_timestamp,
            "is_segment": True,
            "is_end": False,
        }
        todam_table.put_item(Item=item)

        # Get the user's email address
        user_email = user_response["Item"]["email"]
        email_subject = "Recording Started"
        email_body = (
            f"Hi, the recording has started for your message in group {group_id}."
        )

        try:
            ses_client.send_email(
                Source="TODAM <ptqwe20020413@gmail.com>",
                Destination={"ToAddresses": [user_email]},
                Message={
                    "Subject": {"Data": email_subject},
                    "Body": {"Text": {"Data": email_body}},
                },
            )
            print(f"Email sent to {user_email}")
        except ClientError as e:
            print(f"Error sending email: {e.response['Error']['Message']}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    if content == "end recording":
        # Check if the user is registered and verified
        user_response = registered_user_table.get_item(Key={"user_id": user_id})
        if "Item" not in user_response or not user_response["Item"].get(
            "is_verified", False
        ):
            print("User is not registered or not verified, end recording failed.")
            return {
                "statusCode": 403,
                "body": json.dumps("User is not registered or not verified."),
            }

        response = todam_table.query(
            IndexName="GroupTimeIndex",
            KeyConditionExpression=boto3.dynamodb.conditions.Key("group_id").eq(
                group_id
            ),
            FilterExpression=Attr("is_segment").eq(True) & Attr("is_end").eq(False),
        )
        items = response.get("Items", [])
        if items:
            last_item = items[-1]
            last_item["end_timestamp"] = send_timestamp
            last_item["is_message"] = False
            last_item["is_end"] = True
            last_item["segment_name"] = (
                f"{convert_timestamp_to_utc_plus_8(int(last_item['start_timestamp']))}_{convert_timestamp_to_utc_plus_8(int(last_item['end_timestamp']))}"
            )
            todam_table.put_item(Item=last_item)

            # Get the user's email address
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

            try:
                ses_client.send_email(
                    Source="TODAM <ptqwe20020413@gmail.com>",
                    Destination={"ToAddresses": [user_email]},
                    Message={
                        "Subject": {"Data": email_subject},
                        "Body": {"Text": {"Data": email_body}},
                    },
                )
                print(f"Email sent to {user_email} about recording ended")
            except ClientError as e:
                print(f"Error sending email: {e.response['Error']['Message']}")
            except Exception as e:
                print(f"An unexpected error occurred: {e}")

    # Check if the message is a registration request
    registration_match = re.match(r"/register (\S+@ecloudvalley.com)", content)
    if registration_match:
        email = registration_match.group(1)
        apply_registration(user_id, email)

    return {
        "statusCode": 200,
        "body": json.dumps(item),
    }
