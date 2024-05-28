import os

# Environment variables
TODAM_TABLE_NAME = os.environ.get("TODAM_TABLE", "todam_table")
REGISTERED_USER_TABLE_NAME = "registered_user_table"
VERIFY_REGISTRATION_API_URL = f"https://{os.environ.get('VERIFY_REGISTRATION_API_URL')}.execute-api.us-east-1.amazonaws.com/dev/verify-registration"
PARSE_IMAGE_FIFO_QUEUE_URL = os.environ["PARSE_IMAGE_FIFO_QUEUE_URL"]
PARSE_IMAGE_LAMBDA_FUNCTION_NAME = os.environ["PARSE_IMAGE_LAMBDA_FUNCTION_NAME"]
S3_BUCKET = os.environ["S3_BUCKET"]

# File paths
STICKERS_JSON_PATH = "stickers.json"

# Image extensions
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"}

# Email source
EMAIL_SOURCE = "TODAM <ptqwe20020413@gmail.com>"
