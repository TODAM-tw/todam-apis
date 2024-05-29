import json
import logging
from typing import List

import boto3
from boto3.dynamodb.conditions import Attr, Key

# Set up logger
logger = logging.getLogger()
logger.setLevel("INFO")

# Connect to DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("todam_table")


def format_and_condense_messages(messages: List[dict]) -> str:
    formatted_messages = [
        f'{message["user_type"]}: {message["content"]}' for message in messages
    ]
    return "\\n".join(formatted_messages)


def lambda_handler(event, context):
    logger.info("Lambda function started with event: %s", event)

    # Extract segment_id from query parameters
    segment_id = event["queryStringParameters"].get("segment_id")
    output_format = event["queryStringParameters"].get(
        "output"
    )  # Get the 'output' query parameter

    if not segment_id:
        logger.error("Missing segment_id in query parameters")
        return {"statusCode": 400, "body": "Missing segment_id in query parameters"}

    # Retrieve the segment details from DynamoDB
    try:
        segment_response = table.get_item(Key={"id": segment_id})
        segment = segment_response.get("Item", {})
        if not segment or not segment.get("is_end") or not segment.get("end_timestamp"):
            logger.error(
                "Segment not found or incomplete for segment_id: %s", segment_id
            )
            return {"statusCode": 404, "body": "Segment not found or incomplete"}
    except boto3.exceptions.Boto3Error as e:
        logger.error("Error retrieving segment from DynamoDB: %s", e)
        return {"statusCode": 500, "body": "Error retrieving segment from DynamoDB"}

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

    try:
        # Execute the query on GSI
        response = table.query(**message_query_params)
    except boto3.exceptions.Boto3Error as e:
        logger.error("Error querying messages from DynamoDB: %s", e)
        return {"statusCode": 500, "body": "Error querying messages from DynamoDB"}

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

    if output_format == "text":
        # If output format is 'text', use the format_and_condense_messages function
        formatted_text = format_and_condense_messages(messages)
        logger.info("Returning text format response")
        return {
            "statusCode": 200,
            "body": formatted_text,
            "headers": {"Content-Type": "text/plain"},
        }
    else:
        # Create the response body for standard JSON output
        result = {
            "group_id": segment["group_id"],
            "segment_id": segment_id,
            "start_timestamp": int(segment["start_timestamp"]),
            "end_timestamp": int(segment["end_timestamp"]),
            "messages": messages,
        }

        # Return the formatted response
        logger.info("Returning JSON format response")
        return {
            "statusCode": 200,
            "body": json.dumps(result),
            "headers": {"Content-Type": "application/json"},
        }
