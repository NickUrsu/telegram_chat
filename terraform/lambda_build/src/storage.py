# src/storage.py
import uuid
import boto3
import datetime
from .settings import DYNAMODB_TABLE, S3_BUCKET
from .models import convert_numbers_to_decimal

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(DYNAMODB_TABLE)

def now_iso():
    return datetime.datetime.utcnow().isoformat()

def save_image(file_bytes: bytes, user_id: str) -> str:
    key = f"{user_id}/{uuid.uuid4()}.jpg"

    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=file_bytes,
        ContentType="image/jpeg",
    )
    return key

def save_food_log(user_id: str, data: dict):
    item = {
        "user_id": str(user_id),
        "timestamp": now_iso(),
        **convert_numbers_to_decimal(data),
    }
    table.put_item(Item=item)

def get_last_log(user_id: str) -> dict | None:
    """Return the most recent food log for this user, or None if there are none."""
    from boto3.dynamodb.conditions import Key
    response = table.query(
        KeyConditionExpression=Key("user_id").eq(str(user_id)),
        ScanIndexForward=False,  # descending by timestamp
        Limit=1,
    )
    items = response.get("Items", [])
    return items[0] if items else None

def delete_log(user_id: str, timestamp: str):
    """Delete a food log by its composite primary key."""
    table.delete_item(Key={"user_id": str(user_id), "timestamp": timestamp})

