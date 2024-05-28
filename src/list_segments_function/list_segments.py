import json
import logging

import boto3
from boto3.dynamodb.conditions import And, Attr

# Set up logger
logger = logging.getLogger()
logger.setLevel("INFO")

# Connect to DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("todam_table")


def lambda_handler(event, context):
    logger.info("Lambda function started with event: %s", event)

    # Always filter out segments that are not resolved
    base_filter = Attr("is_segment").eq(True) & (
        Attr("is_resolved").eq(False) | Attr("is_resolved").not_exists()
    )

    # Check if query string parameters are present and contain group_id
    group_id = (
        event.get("queryStringParameters", {}).get("group_id")
        if event.get("queryStringParameters")
        else None
    )

    # Construct filter expression based on group_id presence
    if group_id:
        filter_expression = And(base_filter, Attr("group_id").eq(group_id))
        logger.info("Filter expression constructed with group_id: %s", group_id)
    else:
        filter_expression = base_filter
        logger.info("Filter expression constructed without group_id")

    # Prepare the scan parameters with the constructed filter expression
    scan_params = {"FilterExpression": filter_expression}

    try:
        # Execute the scan on the table
        response = table.scan(**scan_params)
        logger.info("DynamoDB scan response: %s", response)
    except boto3.exceptions.Boto3Error as e:
        logger.error("Error scanning DynamoDB table: %s", e)
        return {"statusCode": 500, "body": "Error scanning DynamoDB table"}

    # Process the response to format it as required
    segments = [
        {
            "segment_id": item.get(
                "segment_id", "Unknown"
            ),  # Default to "Unknown" if not found
            "segment_name": item.get("segment_name", "Unnamed"),  # Default to "Unnamed"
            "group_id": item.get("group_id", "No Group"),  # Default to "No Group"
        }
        for item in response.get("Items", [])
    ]

    # Create the response body
    result = {
        "segments": segments,
    }

    # Return the formatted response
    logger.info("Lambda function completed successfully")
    return {
        "statusCode": 200,
        "body": json.dumps(result),
        "headers": {"Content-Type": "application/json"},
    }
