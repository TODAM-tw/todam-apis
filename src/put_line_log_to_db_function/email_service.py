import logging

import boto3
from botocore.exceptions import ClientError

# Initialize AWS SES client
ses_client = boto3.client("ses")

# Configure logger
logger = logging.getLogger(__name__)
logger.setLevel("INFO")

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
        logger.info("Email sent to %s", to_address)
        return response
    except ClientError as e:
        logger.error("Error sending email: %s", e.response["Error"]["Message"])
        raise
    except Exception as e:
        logger.error("An unexpected error occurred: %s", e)
        raise
