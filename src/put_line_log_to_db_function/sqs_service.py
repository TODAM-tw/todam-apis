import json
import logging

import boto3
from botocore.exceptions import ClientError

# Initialize AWS SQS client
sqs = boto3.client("sqs")

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel("INFO")


def send_message_to_sqs(
    queue_url: str, message: dict, message_group_id: str = "default_message_group_id"
) -> dict:
    try:
        response = sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message),
            MessageGroupId=message_group_id,
        )
        logger.info(f"Message sent successfully. MessageId: {response['MessageId']}")
        return response
    except ClientError as e:
        logger.error(f"Error sending message to SQS: {e.response['Error']['Message']}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise
