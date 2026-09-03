"""
Отправка сообщений в Telegram-канал через Bot API.

Нужны две переменные окружения (задаются как секреты в GitHub Actions):
  TELEGRAM_BOT_TOKEN — токен бота, который выдаёт @BotFather
  TELEGRAM_CHAT_ID   — @username канала (если канал публичный)
                       или числовой ID (если приватный)
"""

import os
import time
import requests

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"


def send_message(text: str, disable_preview: bool = False, max_attempts: int = 3) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("[telegram] Не заданы TELEGRAM_BOT_TOKEN и/или TELEGRAM_CHAT_ID")
        return False

    url = TELEGRAM_API_URL.format(token=token, method="sendMessage")
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": disable_preview,
    }

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(url, json=payload, timeout=20)
        except requests.RequestException as e:
            print(f"[telegram] Сетевая ошибка (попытка {attempt}/{max_attempts}): {e}")
            time.sleep(3)
            continue

        if resp.status_code == 200:
            return True

        if resp.status_code == 429:
            # Превышен лимит запросов — Telegram сам говорит, сколько подождать
            try:
                retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
            except ValueError:
                retry_after = 5
            print(f"[telegram] Превышен лимит, жду {retry_after} сек.")
            time.sleep(retry_after + 1)
            continue

        print(f"[telegram] Ошибка отправки (попытка {attempt}/{max_attempts}): "
              f"{resp.status_code} {resp.text}")
        time.sleep(3)

    return False
