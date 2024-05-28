import logging

import boto3
from config import REGISTERED_USER_TABLE_NAME, TODAM_TABLE_NAME

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
todam_table = dynamodb.Table(TODAM_TABLE_NAME)
registered_user_table = dynamodb.Table(REGISTERED_USER_TABLE_NAME)

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def put_item_to_todam_table(item):
    try:
        todam_table.put_item(Item=item)
        logger.info(f"Item put to {TODAM_TABLE_NAME} table successfully.")
    except Exception as e:
        logger.error(f"Error putting item to {TODAM_TABLE_NAME} table: {e}")
        raise


def get_registered_user(user_id):
    try:
        response = registered_user_table.get_item(Key={"user_id": user_id})
        return response
    except Exception as e:
        logger.error(f"Error getting item from {REGISTERED_USER_TABLE_NAME}: {e}")
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
        logger.error(f"Error querying {TODAM_TABLE_NAME} table: {e}")
        raise
