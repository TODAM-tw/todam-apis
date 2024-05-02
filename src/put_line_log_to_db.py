import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Attr

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
todam_table = dynamodb.Table("todam_table")
registered_user_table = dynamodb.Table("registered_user_table")


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


def get_user_type_by_id(user_id: str) -> str:
    response = registered_user_table.get_item(Key={"user_id": user_id})
    if "Item" in response:
        return "TAM"
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

    return {
        "statusCode": 200,
        "body": json.dumps(item),
    }
