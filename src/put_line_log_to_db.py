import json
import os
import re
import uuid
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Attr

s3 = boto3.client("s3")
ses_client = boto3.client("ses")
dynamodb = boto3.resource("dynamodb")
todam_table = dynamodb.Table("todam_table")
registered_user_table = dynamodb.Table("registered_user_table")
verify_registration_api_url = f"https://{os.environ.get('VERIFY_REGISTRATION_API_URL')}.execute.api.us-east-1.amazonaws.com/dev/verify-registration"


def convert_timestamp_to_utc_plus_8(timestamp: int) -> str:
    # Convert milliseconds to seconds
    if timestamp > 1e10:  # Check if timestamp is likely in milliseconds
        timestamp /= 1000  # Convert from milliseconds to seconds

    utc_time = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    utc_plus_8 = timezone(timedelta(hours=8))
    time_in_utc_plus_8 = utc_time.astimezone(utc_plus_8)

    format = "%Y-%m-%d %H:%M:%S"
    time_in_utc_plus_8 = time_in_utc_plus_8.strftime(format)

    return time_in_utc_plus_8


def apply_registration(user_id: str, email: str) -> None:
    # Construct the registration link
    random_code = str(uuid.uuid4())
    registration_url = (
        verify_registration_api_url + f"?user_id={user_id}&code={random_code}"
    )

    # Email content
    email_body = (
        f"Please click on the link to complete your registration: {registration_url}"
    )
    email_subject = "Complete Your Registration"

    # Create a new user item in registered_user_table
    current_time = datetime.now(timezone.utc)
    unix_timestamp_millis = int(current_time.timestamp() * 1000)
    item = {
        "user_id": user_id,
        "code": random_code,
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
        Source="ptqwe20020413@gmail.com",
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
    print("Triggered by S3 Put event")
    print("=====================================")
    print("Event:", event)
    print("=====================================")

    bucket = os.environ["S3_BUCKET"]
    key = event["Records"][0]["s3"]["object"]["key"]

    obj = s3.get_object(Bucket=bucket, Key=key)
    data = obj["Body"].read().decode("utf-8")
    data = json.loads(data)

    print("Lines:")
    print(data)

    # Extract data
    message_type = data["events"][0]["message"]["type"]
    message_id = data["events"][0]["message"]["id"]
    content = data["events"][0]["message"]["text"]
    group_id = data["events"][0]["source"]["groupId"]
    user_id = data["events"][0]["source"]["userId"]
    send_timestamp = data["events"][0]["timestamp"]

    # Generate UUID
    random_uuid = str(uuid.uuid4())
    uuid_no_hyphen = "".join(random_uuid.split("-"))

    # Put data to DynamoDB
    item = {
        "id": uuid_no_hyphen,
        "message_type": message_type,
        "message_id": message_id,
        "content": content,
        "group_id": group_id,
        "user_id": user_id,
        "user_type": get_user_type_by_id(user_id),
        "send_timestamp": send_timestamp,
        "is_segment": False,
        "is_message": True,
    }

    todam_table.put_item(Item=item)

    if content == "start recording":
        uuid_no_hyphen = "".join(str(uuid.uuid4()).split("-"))
        item = {
            "id": uuid_no_hyphen,
            "segment_id": uuid_no_hyphen,
            "start_timestamp": send_timestamp,
            "group_id": group_id,
            "message_id": message_id,
            "user_id": user_id,
            "send_timestamp": send_timestamp,
            "is_segment": True,
            "is_end": False,
        }
        todam_table.put_item(Item=item)

    if content == "end recording":
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
    # Check if the message is a registration request
    registration_match = re.match(r"/register (\S+@ecloudvalley.com)", content)
    if registration_match:
        email = registration_match.group(1)
        apply_registration(user_id, email)

    return {
        "statusCode": 200,
        "body": json.dumps(item),
    }
