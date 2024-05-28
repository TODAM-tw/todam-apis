import logging

import boto3
from botocore.exceptions import ClientError

# Initialize AWS SES client
ses_client = boto3.client("ses")

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EMAIL_SOURCE = "TODAM <ptqwe20020413@gmail.com>"


def send_email(to_address, subject, body):
    try:
        response = ses_client.send_email(
            Source=EMAIL_SOURCE,
            Destination={"ToAddresses": [to_address]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": body}},
            },
        )
        logger.info(f"Email sent to {to_address}")
        return response
    except ClientError as e:
        logger.error(f"Error sending email: {e.response['Error']['Message']}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise
