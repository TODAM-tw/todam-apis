import json
import os

import boto3

s3 = boto3.client("s3")


def lambda_handler(event, context):
    print("Triggered by S3 Put event")
    print("=====================================")
    print("Event:", event)
    print("=====================================")

    bucket = os.environ["S3_BUCKET"]
    key = event["Records"][0]["s3"]["object"]["key"]

    obj = s3.get_object(Bucket=bucket, Key=key)
    lines = obj["Body"].read().decode("utf-8").splitlines()

    print("Lines:")
    print(lines)

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": "hello S3",
                # "location": ip.text.replace("\n", "")
            }
        ),
    }
