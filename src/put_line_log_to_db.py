import json

import boto3

# import requests


def lambda_handler(event, context):

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "hello S3",
                # "location": ip.text.replace("\n", "")
            }
        ),
    }
