import json
import os
import uuid

import boto3

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
todam_table = dynamodb.Table("todam_table")
registered_user_table = dynamodb.Table("registered_user_table")


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
    }

    todam_table.put_item(Item=item)

    return {
        "statusCode": 200,
        "body": json.dumps(item),
    }
