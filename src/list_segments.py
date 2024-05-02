import json

import boto3
from boto3.dynamodb.conditions import And, Attr

# Connect to DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("todam_table")


def lambda_handler(event, context):
    # Always filter to ensure that only segments are returned
    base_filter = Attr("is_segment").eq(True)

    # Check if query string parameters are present and contain group_id
    group_id = (
        event.get("queryStringParameters", {}).get("group_id")
        if event.get("queryStringParameters")
        else None
    )

    # Construct filter expression based on group_id presence
    if group_id:
        filter_expression = And(base_filter, Attr("group_id").eq(group_id))
    else:
        filter_expression = base_filter

    # Prepare the scan parameters with the constructed filter expression
    scan_params = {"FilterExpression": filter_expression}

    # Execute the scan on the table
    response = table.scan(**scan_params)
    print("Response: ", response)

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
    return {
        "statusCode": 200,
        "body": json.dumps(result),
        "headers": {"Content-Type": "application/json"},
    }
