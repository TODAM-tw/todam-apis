import json
import os
import time
import uuid

import boto3

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("todam_table")


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
    message_id = data["events"][0]["message"]["id"]
    group_id = data["events"][0]["source"]["groupId"]
    user_id = data["events"][0]["source"]["userId"]
    send_timestamp = data["events"][0]["timestamp"]

    # Generate UUID
    random_uuid = str(uuid.uuid4())
    uuid_no_hyphen = "".join(random_uuid.split("-"))
    random_uuid_for_segment = str(uuid.uuid4())
    segment_uuid = "".join(random_uuid_for_segment.split("-"))

    # Put data to DynamoDB
    current_timestamp = int(time.time())
    item = {
        "id": uuid_no_hyphen,
        "segment_id": segment_uuid,
        "start_timestamp": current_timestamp,
        "group_id": group_id,
        "message_id": message_id,
        "user_id": user_id,
        "send_timestamp": send_timestamp,
    }

    table.put_item(Item=item)

    return {
        "statusCode": 200,
        "body": json.dumps(item),
    }
