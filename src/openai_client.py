# src/openai_client.py
import json
import time
import requests
from .settings import OPENAI_API_KEY, OPENAI_MODEL

import base64

def call_openai(prompt: str, image_bytes: bytes = None) -> dict:
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    user_content = [{"type": "text", "text": prompt}]
    
    if image_bytes:
        base64_image = base64.b64encode(image_bytes).decode('utf-8')
        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{base64_image}"
            }
        })

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You extract nutrition info and ALWAYS return valid JSON only. "
                    "Schema: {\"items\": [{food_name, kcal, protein, carbs, fat}, ...]}. "
                    "If the input is NOT food, return {\"items\": [], \"error\": \"not_food\"}. "
                    "If unknown food, estimate conservatively."
                ),
            },
            {"role": "user", "content": user_content},
        ],
        "temperature": 0.2,
    }

    for attempt in range(3):
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20,
        )

        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue

        r.raise_for_status()
        
        content = r.json()["choices"][0]["message"]["content"]
        print(f"DEBUG: OpenAI Raw Content: {content}") # Use print or logger if configured
        
        # Clean markdown code blocks
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        
        content = content.strip()
        
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Fallback or re-raise with context
            print(f"ERROR: Failed to parse JSON: {content}")
            raise

    raise RuntimeError("OpenAI rate limit exceeded")


# Max characters of nutrition data to include in the feedback prompt.
# Keeps the request cheap and the reply short enough for a chat message.
_FEEDBACK_MAX_CHARS = 1200


def get_report_feedback(period: str, report_text: str, profile: dict) -> str:
    """
    Ask OpenAI to provide short personalised coaching commentary on a
    daily/weekly nutrition report, given the user's registered profile.

    Returns a plain-text string (no HTML) ready to append to the Telegram message.
    """
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    goal        = profile.get("goal", "unknown")
    kcal_target = profile.get("kcal_target", "unknown")
    weight_kg   = profile.get("weight_kg", "unknown")
    gender      = profile.get("gender", "unknown")
    summary     = profile.get("summary", "")

    # Truncate report text so the total prompt stays reasonable
    truncated_report = report_text[:_FEEDBACK_MAX_CHARS]

    system_prompt = (
        "You are a friendly, knowledgeable nutrition coach. "
        "The user has shared their nutrition data for a period. "
        "Give concise, actionable feedback in 3-5 short sentences. "
        "Be encouraging but honest. Use simple language. "
        "Do NOT use markdown formatting or bullet points — plain text only, "
        "suitable for a Telegram chat message. "
        "Do NOT repeat the nutrition numbers back to the user verbatim."
    )

    profile_line = (
        f"User profile: {gender}, {weight_kg} kg, goal: {goal}, "
        f"daily calorie target: {kcal_target} kcal."
    )
    if summary:
        profile_line += f"\nProfile details: {summary}"

    user_prompt = (
        f"{profile_line}\n\n"
        f"{period.capitalize()} nutrition summary:\n{truncated_report}"
    )

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 1.0,
        "max_tokens": 220,
    }

    for attempt in range(3):
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20,
        )
        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()

    raise RuntimeError("OpenAI rate limit exceeded")


def calculate_tdee(profile_text: str) -> dict:
    """
    Send user's free-text profile to OpenAI and get back a structured TDEE result.
    Returns a dict with keys: age, gender, height_cm, weight_kg, goal, kcal_target, summary
    """
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    system_prompt = (
        "You are a nutrition expert. Extract the user's profile from their message and "
        "calculate their daily calorie target using the Mifflin-St Jeor equation adjusted "
        "for their activity level and goal.\n\n"
        "ALWAYS return valid JSON only, with this exact schema:\n"
        "{\n"
        "  \"age\": <integer>,\n"
        "  \"gender\": \"male\" or \"female\",\n"
        "  \"height_cm\": <integer>,\n"
        "  \"weight_kg\": <number>,\n"
        "  \"goal\": \"fat loss\" or \"maintenance\" or \"muscle gain\",\n"
        "  \"kcal_target\": <integer, daily calorie target>,\n"
        "  \"summary\": \"<2-3 sentence personalised explanation with the calorie target and macro split>\"\n"
        "}\n\n"
        "If any required field cannot be determined from the message, make a reasonable assumption "
        "and note it in the summary."
    )

    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": profile_text},
        ],
        "temperature": 0.3,
    }

    for attempt in range(3):
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=20,
        )

        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue

        r.raise_for_status()

        content = r.json()["choices"][0]["message"]["content"]

        # Strip markdown code fences if present
        for prefix in ("```json", "```"):
            if content.startswith(prefix):
                content = content[len(prefix):]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        return json.loads(content)

    raise RuntimeError("OpenAI rate limit exceeded")

