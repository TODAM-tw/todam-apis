import json
import os

import boto3
import requests

# Environment variables
API_URL = os.getenv(
    "API_URL",
    "https://d0e7i3hn2k.execute-api.us-west-2.amazonaws.com/api-gateway-for-intern?",
)

# Connect to DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("todam_table")

# Set up boto3 client for SSM
ssm = boto3.client("ssm")


def get_api_key():
    """Retrieve and cache the API key from AWS SSM Parameter Store."""
    parameter = ssm.get_parameter(Name="CreateTicketApiKey", WithDecryption=True)
    return parameter["Parameter"]["Value"]


api_key = get_api_key()


def api_create_ticket(payload: dict) -> dict:
    """Send a POST request to create a ticket."""
    headers = {"x-api-key": api_key}
    response = requests.post(API_URL, json=payload, headers=headers)
    try:
        return response.json()
    except ValueError:  # includes simplejson.decoder.JSONDecodeError
        return {"statusCode": 500, "body": "Invalid JSON response"}


def lambda_handler(event, context):
    """Lambda function to handle incoming requests."""
    try:
        payload = json.loads(event["body"])
    except json.JSONDecodeError:
        return {"statusCode": 400, "body": "Invalid JSON format"}

    create_ticket_payload = {
        "ticket_subject": payload.get("ticket_subject"),
        "ticket_description": payload.get("ticket_description"),
        "department_id": payload.get("department_id"),
    }

    segment_id = payload.get("segment_id")
    if not segment_id:
        return {"statusCode": 400, "body": "Missing segment_id"}

    result = api_create_ticket(payload=create_ticket_payload)

    if result.get("statusCode") != 200:
        return {
            "statusCode": result.get("statusCode"),
            "body": json.dumps(result),
            "headers": {"Content-Type": "application/json"},
        }

    try:
        table.update_item(
            Key={"id": segment_id},
            UpdateExpression="set is_resolved = :r",
            ExpressionAttributeValues={":r": True},
        )
    except boto3.exceptions.Boto3Error as e:
        return {"statusCode": 500, "body": "Failed to update DynamoDB", "error": str(e)}

    return {
        "statusCode": 200,
        "body": json.dumps(result),
        "headers": {"Content-Type": "application/json"},
    }
