# src/handler.py
import json
from datetime import datetime, timezone, timedelta

import logging

from .telegram import extract_message, download_file, send_message, send_photo
from .openai_client import call_openai, calculate_tdee, get_report_feedback
from .storage import save_image, save_food_log, get_last_log, delete_log
from .settings import S3_BUCKET
from .reports import query_logs, aggregate_by_day, build_text_report, get_daily_totals
from .chart import generate_chart
from .user_profile import (
    save_user_profile, get_user_profile,
    create_session, get_session, delete_session,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ── Static text ───────────────────────────────────────────────────────────────

START_MSG = (
    "👋 <b>Welcome to your personal nutrition tracker!</b>\n\n"
    "I help you log meals, track macros, and understand your progress.\n\n"
    "<b>📸 Logging food</b>\n"
    "• Send a <b>photo</b> of your meal — I'll extract nutrition info automatically\n"
    "• Send a <b>text message</b> like <i>\"2 eggs, toast with butter, coffee\"</i>\n\n"
    "<b>📋 Commands</b>\n"
    "/daily — today's nutrition summary\n"
    "/weekly — 7-day avg nutrition summary + chart\n"
    "/delete — remove the last logged meal (within 5 min)\n"
    "/register — set up your profile & get your daily calorie target\n"
    "/start — show this help message\n\n"
    "Let's get started! Log your first meal by sending a photo or text. 🥗"
)

REGISTER_PROMPT = (
    "📝 <b>Let's set up your profile!</b>\n\n"
    "To calculate your daily calorie needs, please send me:\n"
    "• Age\n"
    "• Sex (male/female)\n"
    "• Height (cm)\n"
    "• Weight (kg)\n"
    "• How many days per week you train\n"
    "• Type of training (e.g., weights, cardio, martial arts)\n"
    "• Your goal (fat loss / maintenance / muscle gain)\n\n"
    "You can reply in one message like this:\n"
    "<i>\"34, male, 174 cm, 81 kg, train 4x/week weights + running, goal: fat loss\"</i>"
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def respond(status=200, body="ok"):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def handle_report(user_id: str, period: str, days: int):
    """Fetch logs, build text report, optionally send chart, optionally add AI feedback."""
    logger.info(f"Generating {period} report for user={user_id}")
    try:
        logs = query_logs(user_id, days)
        aggregated = aggregate_by_day(logs)

        text = build_text_report(aggregated, period)

        # Only send chart for weekly reports — daily chart adds little value
        if period == "weekly":
            chart_bytes = generate_chart(aggregated, period)
            if chart_bytes:
                send_photo(user_id, chart_bytes)

        # Append personalised AI feedback if the user has a complete profile with a goal
        profile = get_user_profile(str(user_id))
        if profile and profile.get("goal") and profile.get("kcal_target"):
            logger.info(f"Fetching AI feedback for user={user_id}, period={period}")
            try:
                feedback = get_report_feedback(period, text, profile)
                text += f"\n\n💬 <b>Coach's take:</b>\n{feedback}"
            except Exception:
                logger.error("Failed to get AI report feedback", exc_info=True)
                # Non-fatal — still send the plain report

        send_message(user_id, text)
        logger.info(f"{period} report sent to user={user_id}")
    except Exception:
        logger.error(f"Error generating {period} report", exc_info=True)
        send_message(user_id, f"Sorry, I couldn't generate your {period} report. Please try again later.")


def handle_delete(user_id: str):
    """Delete the most recent food log if it was registered within the last 5 minutes."""
    logger.info(f"Handling /delete for user={user_id}")
    last = get_last_log(user_id)

    if not last:
        send_message(user_id, "No meals were registered in the last 5 minutes.")
        return

    ts_str = last.get("timestamp", "")
    try:
        # Timestamps are stored as ISO without timezone — treat as UTC
        logged_at = datetime.fromisoformat(ts_str.rstrip("Z")).replace(tzinfo=timezone.utc)
    except ValueError:
        logger.error(f"Could not parse timestamp: {ts_str}")
        send_message(user_id, "No meals were registered in the last 5 minutes.")
        return

    age = datetime.now(timezone.utc) - logged_at
    if age > timedelta(minutes=5):
        send_message(user_id, "No meals were registered in the last 5 minutes.")
        return

    food_name = last.get("food_name", "your last meal")
    delete_log(user_id, ts_str)
    logger.info(f"Deleted log timestamp={ts_str} for user={user_id}")
    send_message(user_id, f"✅ Deleted: <b>{food_name}</b>")


def handle_register(user_id: str):
    """Start the /register flow — save session and prompt for profile info."""
    create_session(str(user_id), state="awaiting_profile")
    send_message(user_id, REGISTER_PROMPT)
    logger.info(f"Registration flow started for user={user_id}")


def handle_profile_response(user_id: str, text: str):
    """Called when a user with an active session sends their profile text."""
    logger.info(f"Processing profile response for user={user_id}")
    try:
        profile = calculate_tdee(text)
        profile["raw_answer"] = text
        save_user_profile(str(user_id), profile)
        delete_session(str(user_id))

        summary = profile.get("summary", "")
        kcal = profile.get("kcal_target", "?")
        send_message(
            user_id,
            f"✅ <b>Profile saved!</b>\n\n"
            f"🎯 Your daily calorie target: <b>{kcal} kcal</b>\n\n"
            f"{summary}\n\n"
            f"Start logging your meals and use /daily or /weekly to track progress!"
        )
        logger.info(f"Profile saved for user={user_id}, kcal_target={kcal}")
    except Exception:
        logger.error("Error processing profile response", exc_info=True)
        send_message(user_id, "Sorry, I couldn't process your profile. Please try /register again.")
        delete_session(str(user_id))


# ── Lambda entrypoint ─────────────────────────────────────────────────────────

def lambda_handler(event, context, debug=False):
    logger.info("Received event")
    try:
        user_id, msg_type, payload = extract_message(event)
        logger.info(f"Extracted message: user_id={user_id}, type={msg_type}")

        image_bytes = None

        if msg_type == "text":
            cmd = payload.strip().lower()

            # ── Commands ──────────────────────────────────────────────────────
            if cmd == "/start":
                send_message(user_id, START_MSG)
                return respond(200)

            if cmd == "/delete":
                handle_delete(user_id)
                return respond(200)

            if cmd in ("/daily", "/weekly"):
                period = "daily" if cmd == "/daily" else "weekly"
                days = 1 if period == "daily" else 7
                handle_report(user_id, period, days)
                return respond(200)

            if cmd == "/register":
                handle_register(user_id)
                return respond(200)

            # ── Session check: awaiting profile from /register ─────────────
            session = get_session(str(user_id))
            if session and session.get("state") == "awaiting_profile":
                handle_profile_response(user_id, payload)
                return respond(200)

            # ── Normal food logging ───────────────────────────────────────
            prompt = f"Food input: {payload}"

        elif msg_type == "photo":
            file_id, caption = payload
            image_bytes = download_file(file_id)
            save_image(image_bytes, user_id)
            if caption:
                prompt = f"Extract nutrition info from this image. Additional context from the user: {caption}"
            else:
                prompt = "Extract nutrition info from this image."

        else:
            return respond(200)

        logger.info("Calling OpenAI")
        nutrition_response = call_openai(prompt, image_bytes=image_bytes)
        logger.info(f"OpenAI response: {json.dumps(nutrition_response)}")

        if "error" in nutrition_response and nutrition_response["error"] == "not_food":
            send_message(user_id, "I couldn't identify any food in that message.")
            return respond(200)

        # Aggregate items
        items = nutrition_response.get("items", [])
        if not items:
            items = [nutrition_response] if "food_name" in nutrition_response else []

        total_nutrition = {"food_name": [], "kcal": 0, "protein": 0, "carbs": 0, "fat": 0}
        for item in items:
            total_nutrition["food_name"].append(item.get("food_name", "Unknown"))
            total_nutrition["kcal"]    += item.get("kcal") or 0
            total_nutrition["protein"] += item.get("protein") or 0
            total_nutrition["carbs"]   += item.get("carbs") or 0
            total_nutrition["fat"]     += item.get("fat") or 0

        final_record = {
            "food_name": ", ".join(total_nutrition["food_name"]),
            "kcal":      total_nutrition["kcal"],
            "protein":   total_nutrition["protein"],
            "carbs":     total_nutrition["carbs"],
            "fat":       total_nutrition["fat"],
            "raw_items": items,
        }

        now = datetime.now(timezone.utc)
        final_record["date"]      = now.date().isoformat()
        final_record["timestamp"] = now.isoformat()

        logger.info(f"Saving food log: {final_record}")
        save_food_log(user_id, final_record)

        daily = get_daily_totals(user_id)
        msg = (
            f"✅ Logged: <b>{final_record['food_name']}</b>\n"
            f"🔥 {final_record['kcal']} kcal  |  "
            f"🥩 P: {final_record['protein']}g  "
            f"🍞 C: {final_record['carbs']}g  "
            f"🧈 F: {final_record['fat']}g\n"
            f"——————————————————\n"
            f"Daily total: 🔥 {daily['kcal']:.0f} kcal  "
            f"🥩 P: {daily['protein']:.1f}g  "
            f"🍞 C: {daily['carbs']:.1f}g  "
            f"🧈 F: {daily['fat']:.1f}g"
        )
        send_message(user_id, msg)
        logger.info("Message sent to user")

        if debug:
            return respond(200, final_record)
        return respond(200)

    except Exception as e:
        logger.error("Error processing request", exc_info=True)
        return respond(500, {"error": str(e)})
