import json
import logging
import os

import boto3
import requests

# Set up logger
logger = logging.getLogger()
logger.setLevel("INFO")

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
    logger.info("API key retrieved from SSM")
    return parameter["Parameter"]["Value"]


api_key = get_api_key()


def api_create_ticket(payload: dict) -> dict:
    """Send a POST request to create a ticket."""
    headers = {"x-api-key": api_key}
    response = requests.post(API_URL, json=payload, headers=headers)
    logger.info("Sent POST request to API with payload: %s", payload)
    try:
        return response.json()
    except ValueError:  # includes simplejson.decoder.JSONDecodeError
        logger.error("Invalid JSON response from API")
        return {"statusCode": 500, "body": "Invalid JSON response"}


def lambda_handler(event, context):
    """Lambda function to handle incoming requests."""
    logger.info("Lambda function started with event: %s", event)

    try:
        payload = json.loads(event["body"])
        logger.info("Received payload: %s", payload)
    except json.JSONDecodeError:
        logger.error("Invalid JSON format")
        return {"statusCode": 400, "body": "Invalid JSON format"}

    create_ticket_payload = {
        "ticket_subject": payload.get("ticket_subject"),
        "ticket_description": payload.get("ticket_description"),
        "department_id": payload.get("department_id"),
    }

    segment_id = payload.get("segment_id")
    if not segment_id:
        logger.error("Missing segment_id")
        return {"statusCode": 400, "body": "Missing segment_id"}

    result = api_create_ticket(payload=create_ticket_payload)

    if result.get("statusCode") != 200:
        logger.error("API call failed with response: %s", result)
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
        logger.info("Successfully updated DynamoDB for segment_id: %s", segment_id)
    except boto3.exceptions.Boto3Error as e:
        logger.error("Failed to update DynamoDB", exc_info=True)
        return {"statusCode": 500, "body": "Failed to update DynamoDB", "error": str(e)}

    logger.info("Lambda function completed successfully")
    return {
        "statusCode": 200,
        "body": json.dumps(result),
        "headers": {"Content-Type": "application/json"},
    }
