import json
from datetime import datetime, timezone

import boto3

s3 = boto3.client("s3")
ses_client = boto3.client("ses")
dynamodb = boto3.resource("dynamodb")
todam_table = dynamodb.Table("todam_table")
registered_user_table = dynamodb.Table("registered_user_table")


def verify_registration(user_id: str, code: str) -> bool:
    # Get user by user_id
    response = registered_user_table.get_item(Key={"user_id": user_id})

    # Check if user exists
    if "Item" not in response:
        raise ValueError(f"User {user_id} does not exist")

    # Convert current UTC time to a 13-digit Unix timestamp (milliseconds)
    current_time = int(datetime.now(timezone.utc).timestamp() * 1000)

    # Get the apply timestamp from the response (assuming it's already a 13-digit Unix timestamp)
    apply_timestamp = response["Item"]["apply_timestamp"]

    # Check if the registration time is within 24 hours
    if current_time - apply_timestamp > 24 * 3600 * 1000:  # 24 hours in milliseconds
        raise ValueError("Verification code expired")

    # Check if verification code matches
    if response["Item"]["verification_code"] != code:
        raise ValueError("Invalid verification code")

    # Update user to be verified
    registered_user_table.update_item(
        Key={"user_id": user_id},
        UpdateExpression="SET is_verified = :val",
        ExpressionAttributeValues={":val": True},
    )
    return True


def lambda_handler(event, context):

    user_id = event["queryStringParameters"]["user_id"]
    code = event["queryStringParameters"]["code"]

    # Verify registration
    if verify_registration(user_id, code):
        item = {"message": "Registration verified"}
    else:
        item = {"message": "Registration verification failed"}

    return {
        "statusCode": 200,
        "body": json.dumps(item),
    }
