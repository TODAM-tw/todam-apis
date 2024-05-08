import json

import boto3
import requests
from boto3.dynamodb.conditions import And, Attr
import os

# Connect to DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("todam_table")


def api_create_ticket(payload: dict) -> dict:
    request_url = (
        "https://d0e7i3hn2k.execute-api.us-west-2.amazonaws.com/api-gateway-for-intern?"
    )
    headers = {"x-api-key": os.environ["CREATE_TICKET_API_KEY"]}
    response = requests.post(
        request_url,
        json=payload,
        headers=headers,
    )
    return response.json()


def lambda_handler(event, context):
    # Get the api payload
    payload = json.loads(event["body"])

    # Extract the required fields from the payload
    create_ticket_payload = {
        "ticket_subject": payload["ticket_subject"],
        "ticket_description": payload["ticket_description"],
        "department_id": payload["department_id"],
    }

    segment_id = payload["segment_id"]

    # call create ticket api
    result = api_create_ticket(payload=create_ticket_payload)

    # If create ticket api response["statusCode"] not equal to 200, return the response, else update the item's property `is_resolved` to True by segment_id in DynamoDB
    if result["statusCode"] != 200:
        return {
            "statusCode": result["statusCode"],
            "body": json.dumps(result),
            "headers": {"Content-Type": "application/json"},
        }

    # Update item's property `is_resolved` to True by segment_id in DynamoDB
    table.update_item(
        Key={"id": segment_id},
        UpdateExpression="set is_resolved = :r",
        ExpressionAttributeValues={":r": True},
    )

    # Return the formatted response
    return {
        "statusCode": 200,
        "body": json.dumps(result),
        "headers": {"Content-Type": "application/json"},
    }
