"""
Хранение состояния между запусками: что уже было опубликовано в канал,
чтобы не постить одно и то же дважды.

Состояние лежит в файле state.json прямо в репозитории. После каждого
запуска GitHub Actions коммитит обновлённый файл обратно в репозиторий
(это настроено в .github/workflows/bot.yml) — так данные не теряются
между запусками, хотя сам раннер GitHub Actions каждый раз "чистый".
"""

import json
import os

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

# Сколько последних ID хранить в каждом списке. Чем больше — тем меньше
# риск случайно повторить старый пост, но файл будет чуть тяжелее.
MAX_ITEMS_PER_LIST = 2000


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {"posted_deals": [], "posted_news": []}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[state] Не удалось прочитать state.json ({e}), начинаю с чистого состояния")
        return {"posted_deals": [], "posted_news": []}

    data.setdefault("posted_deals", [])
    data.setdefault("posted_news", [])
    return data


def save_state(state: dict) -> None:
    trimmed = {
        "posted_deals": list(state.get("posted_deals", []))[-MAX_ITEMS_PER_LIST:],
        "posted_news": list(state.get("posted_news", []))[-MAX_ITEMS_PER_LIST:],
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)
