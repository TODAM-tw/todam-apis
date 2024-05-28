import os
import uuid
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError
from email_service import send_email

# Initialize AWS clients
dynamodb = boto3.resource("dynamodb")
registered_user_table = dynamodb.Table("registered_user_table")
verify_registration_api_url = f"https://{os.environ.get('VERIFY_REGISTRATION_API_URL')}.execute-api.us-east-1.amazonaws.com/dev/verify-registration"

# Configure logger
import logging

logger = logging.getLogger(__name__)
logger.setLevel("INFO")


def apply_registration(user_id: str, email: str) -> None:
    response = registered_user_table.get_item(Key={"user_id": user_id})
    if "Item" in response:
        if response["Item"].get("is_verified"):
            logger.info("You have already registered.")
            return

        current_time_millis = int(datetime.now(timezone.utc).timestamp() * 1000)
        if current_time_millis - response["Item"]["apply_timestamp"] < 60 * 1000:
            logger.info(
                "Please wait a moment before requesting a new verification email."
            )
            return

    random_code = str(uuid.uuid4())
    registration_url = (
        verify_registration_api_url + f"?user_id={user_id}&code={random_code}"
    )

    email_body = f"Hi {email.split('@')[0]}, Please click on the link to complete your registration:\n {registration_url}"
    email_subject = "Todam - Complete Your Registration"

    current_time = datetime.now(timezone.utc)
    unix_timestamp_millis = int(current_time.timestamp() * 1000)
    item = {
        "user_id": user_id,
        "email": email,
        "name": email.split("@")[0],
        "apply_timestamp": unix_timestamp_millis,
        "verification_code": random_code,
        "is_verified": False,
    }
    registered_user_table.put_item(Item=item)
    logger.info(f"User {email} has applied for registration")

    send_email(email, email_subject, email_body)


def get_user_type_by_id(user_id: str) -> str:
    response = registered_user_table.get_item(Key={"user_id": user_id})
    item = response.get("Item")
    return "TAM" if item and item.get("is_verified", False) else "Client"
