# src/telegram.py
import json
import requests
from .settings import TELEGRAM_BOT_TOKEN

def extract_message(event):
    body = json.loads(event["body"])
    message = body.get("message", {})
    user_id = message["from"]["id"]

    if "text" in message:
        return user_id, "text", message["text"]

    if "photo" in message:
        file_id = message["photo"][-1]["file_id"]
        caption = message.get("caption", "")
        return user_id, "photo", (file_id, caption)

    return user_id, "unknown", None

def download_file(file_id: str) -> bytes:
    info = requests.get(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile",
        params={"file_id": file_id},
        timeout=10,
    ).json()

    if not info.get("ok"):
        raise ValueError(f"Telegram API error: {info}")

    path = info["result"]["file_path"]
    url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{path}"
    return requests.get(url, timeout=20).content

def send_message(user_id: int, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": user_id,
        "text": text,
        "parse_mode": "HTML"
    }
    requests.post(url, json=payload, timeout=10)

def send_photo(user_id: int, photo_bytes: bytes, caption: str = ""):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    requests.post(
        url,
        data={"chat_id": user_id, "caption": caption, "parse_mode": "HTML"},
        files={"photo": ("report.png", photo_bytes, "image/png")},
        timeout=30,
    )
