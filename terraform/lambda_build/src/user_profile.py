# src/user_profile.py
import logging
from datetime import datetime, timezone

import boto3

from .settings import USER_PROFILES_TABLE, SESSIONS_TABLE
from .models import convert_numbers_to_decimal

logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb")
profiles_table = dynamodb.Table(USER_PROFILES_TABLE)
sessions_table = dynamodb.Table(SESSIONS_TABLE)


# ── User Profiles ─────────────────────────────────────────────────────────────

def save_user_profile(user_id: str, profile: dict):
    """
    Persist a user profile to DynamoDB.
    profile must contain: age, gender, height_cm, weight_kg, goal, kcal_target, raw_answer
    """
    item = {
        "user_id": str(user_id),
        "registered_at": datetime.now(timezone.utc).isoformat(),
        **convert_numbers_to_decimal(profile),
    }
    profiles_table.put_item(Item=item)
    logger.info(f"Saved user profile for user_id={user_id}")


def get_user_profile(user_id: str) -> dict | None:
    response = profiles_table.get_item(Key={"user_id": str(user_id)})
    return response.get("Item")


# ── Sessions (for /register two-phase flow) ───────────────────────────────────

def create_session(user_id: str, state: str, ttl_minutes: int = 10):
    """Write a session record with a TTL so DynamoDB auto-cleans it."""
    import time
    ttl = int(time.time()) + ttl_minutes * 60
    sessions_table.put_item(Item={
        "user_id": str(user_id),
        "state": state,
        "ttl": ttl,
    })
    logger.info(f"Session created for user_id={user_id}, state={state}, ttl={ttl_minutes}min")


def get_session(user_id: str) -> dict | None:
    response = sessions_table.get_item(Key={"user_id": str(user_id)})
    return response.get("Item")


def delete_session(user_id: str):
    sessions_table.delete_item(Key={"user_id": str(user_id)})
    logger.info(f"Session deleted for user_id={user_id}")
