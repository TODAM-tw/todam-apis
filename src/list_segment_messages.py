import json

import boto3
from boto3.dynamodb.conditions import Attr, Key

# Connect to DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("todam_table")


def lambda_handler(event, context):
    # Extract segment_id from query parameters
    segment_id = event["queryStringParameters"]["segment_id"]

    # Retrieve the segment details from DynamoDB
    segment_response = table.get_item(Key={"id": segment_id})
    segment = segment_response.get("Item", {})
    if not segment or not segment.get("is_end") or not segment.get("end_timestamp"):
        return {"statusCode": 404, "body": "Segment not found or incomplete"}

    # Query the messages using the timestamps and group_id
    message_query_params = {
        "IndexName": "GroupTimeIndex",
        "KeyConditionExpression": Key("group_id").eq(segment["group_id"])
        & Key("send_timestamp").between(
            segment["start_timestamp"], segment["end_timestamp"]
        ),
        "FilterExpression": Attr("is_message").eq(
            True
        ),  # Filtering for is_message == True
    }

    # Execute the query on GSI
    response = table.query(**message_query_params)

    # Process the response to format it as required
    messages = [
        {
            "user_id": item.get("user_id", "unknown_user_id"),
            "user_type": item.get("user_type", "unknown_user_type"),
            "message_type": item.get("message_type", "unknown_message_type"),
            "content": item.get("content", ""),
            "send_timestamp": int(item["send_timestamp"]),
        }
        for item in response.get("Items", [])
    ]

    # Create the response body
    result = {
        "group_id": segment["group_id"],
        "segment_id": segment_id,
        "start_timestamp": int(segment["start_timestamp"]),
        "end_timestamp": int(segment["end_timestamp"]),
        "messages": messages,
    }

    # Return the formatted response
    return {
        "statusCode": 200,
        "body": json.dumps(result),
        "headers": {"Content-Type": "application/json"},
    }
