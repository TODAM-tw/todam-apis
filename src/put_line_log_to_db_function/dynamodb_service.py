import logging

import boto3
from config import REGISTERED_USER_TABLE_NAME, TODAM_TABLE_NAME

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
todam_table = dynamodb.Table(TODAM_TABLE_NAME)
registered_user_table = dynamodb.Table(REGISTERED_USER_TABLE_NAME)

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel("INFO")


def put_item_to_todam_table(item):
    try:
        todam_table.put_item(Item=item)
        logger.info("Item put to %s table successfully.", TODAM_TABLE_NAME)
    except Exception as e:
        logger.error("Error putting item to %s table: %s", TODAM_TABLE_NAME, e)
        raise


def get_registered_user(user_id):
    try:
        response = registered_user_table.get_item(Key={"user_id": user_id})
        return response
    except Exception as e:
        logger.error("Error getting item from %s: %s", REGISTERED_USER_TABLE_NAME, e)
        raise


def query_todam_table(group_id):
    try:
        response = todam_table.query(
            IndexName="GroupTimeIndex",
            KeyConditionExpression=boto3.dynamodb.conditions.Key("group_id").eq(
                group_id
            ),
            FilterExpression=boto3.dynamodb.conditions.Attr("is_segment").eq(True)
            & boto3.dynamodb.conditions.Attr("is_end").eq(False),
        )
        return response
    except Exception as e:
        logger.error("Error querying %s table: %s", TODAM_TABLE_NAME, e)
        raise
