# src/reports.py
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key, Attr

from .settings import DYNAMODB_TABLE

logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(DYNAMODB_TABLE)


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _date_n_days_ago(n: int) -> str:
    return (datetime.now(timezone.utc).date() - timedelta(days=n - 1)).isoformat()


def query_logs(user_id: str, days: int) -> list[dict]:
    """
    Query DynamoDB for a user's food logs over the last `days` calendar days.
    Returns a list of item dicts with numeric fields converted from Decimal to float.
    """
    start_date = _date_n_days_ago(days)
    today = _today_utc()

    logger.info(
        f"Querying logs for user={user_id}, days={days}, range={start_date}..{today}"
    )

    # Query by partition key (user_id) then filter on the 'date' attribute.
    # We use between on the timestamp sort key to limit the scan range efficiently.
    start_ts = start_date + "T00:00:00"
    end_ts = today + "T23:59:59"

    response = table.query(
        KeyConditionExpression=Key("user_id").eq(str(user_id))
        & Key("timestamp").between(start_ts, end_ts),
    )
    items = response.get("Items", [])

    # Handle pagination
    while "LastEvaluatedKey" in response:
        response = table.query(
            KeyConditionExpression=Key("user_id").eq(str(user_id))
            & Key("timestamp").between(start_ts, end_ts),
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    logger.info(f"Retrieved {len(items)} log items")
    return [_decimal_to_float(item) for item in items]


def _decimal_to_float(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _decimal_to_float(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decimal_to_float(v) for v in obj]
    return obj


def aggregate_by_day(logs: list[dict]) -> dict[str, dict]:
    """
    Aggregate log items by date.
    Returns OrderedDict-like dict: {date_str: {kcal, protein, carbs, fat, entries}}
    sorted chronologically.
    """
    by_day: dict[str, dict] = {}

    for item in logs:
        date = item.get("date") or item.get("timestamp", "")[:10]
        if not date:
            continue

        if date not in by_day:
            by_day[date] = {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "entries": []}

        by_day[date]["kcal"]    += float(item.get("kcal", 0) or 0)
        by_day[date]["protein"] += float(item.get("protein", 0) or 0)
        by_day[date]["carbs"]   += float(item.get("carbs", 0) or 0)
        by_day[date]["fat"]     += float(item.get("fat", 0) or 0)
        by_day[date]["entries"].append(item.get("food_name", ""))

    return dict(sorted(by_day.items()))


def build_text_report(aggregated: dict[str, dict], period_label: str) -> str:
    """
    Build a human-readable text report from aggregated daily data.
    - daily:  shows each day's macros and food names
    - weekly: shows only the total macros over the full date range
    """
    if not aggregated:
        return f"No food logs found for the {period_label} period. Start logging your meals! 🍽️"

    lines = [f"📊 <b>{period_label.capitalize()} Nutrition Report</b>\n"]

    # Calculate totals
    total = {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
    for data in aggregated.values():
        total["kcal"]    += data["kcal"]
        total["protein"] += data["protein"]
        total["carbs"]   += data["carbs"]
        total["fat"]     += data["fat"]

    if period_label == "daily":
        # Per-day breakdown with food names
        for date, data in aggregated.items():
            foods = ", ".join(f for f in data["entries"] if f) or "—"
            lines.append(
                f"📅 <b>{date}</b>\n"
                f"🔥 {data['kcal']:.0f} kcal  |  "
                f"🥩 P: {data['protein']:.1f}g  "
                f"🍞 C: {data['carbs']:.1f}g  "
                f"🧈 F: {data['fat']:.1f}g\n"
                f"🍽️ {foods}\n"
            )
    else:
        # Weekly: date range + per-day averages
        dates = list(aggregated.keys())
        n = len(dates)
        date_range = f"{dates[0]} ~ {dates[-1]}" if n > 1 else dates[0]
        avg_label = f"Avg/day over {n} day{'s' if n != 1 else ''}"
        lines.append(
            f"📅 {date_range}\n"
            f"<i>{avg_label}</i>\n"
            f"🔥 {total['kcal']/n:.0f} kcal  |  "
            f"🥩 P: {total['protein']/n:.1f}g  "
            f"🍞 C: {total['carbs']/n:.1f}g  "
            f"🧈 F: {total['fat']/n:.1f}g"
        )

    return "\n".join(lines)


def get_daily_totals(user_id: str) -> dict:
    """Return today's summed kcal/protein/carbs/fat for a user."""
    logs = query_logs(user_id, days=1)
    aggregated = aggregate_by_day(logs)
    today = _today_utc()
    return aggregated.get(today, {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0})
