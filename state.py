"""
Хранение состояния между запусками: что уже опубликовано, что сейчас
стоит в очереди на публикацию, когда последний раз публиковали каждый
тип материала, и список уже известных боту названий игр (нужен для
защиты названий при переводе новостей).

Состояние лежит в файле state.json прямо в репозитории. После каждого
запуска GitHub Actions коммитит обновлённый файл обратно в репозиторий
(см. .github/workflows/bot.yml) — так данные не теряются между запусками,
хотя сам раннер GitHub Actions каждый раз "чистый".
"""

import json
import os
from datetime import datetime, timezone

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

# Сколько последних записей хранить в каждом списке.
MAX_POSTED_ITEMS = 3000
MAX_KNOWN_TITLES = 500

DEFAULT_STATE = {
    "posted_deals": [],
    "posted_news": [],
    "queue": [],
    "queued_ids": [],
    "last_published": {},        # {"hot": "2026-...", "deal": "...", "news": "..."}
    "known_game_titles": [],     # для защиты названий игр при переводе новостей
}


def _seed_last_published(data: dict) -> None:
    """
    ВАЖНО для корректной работы очереди: если для тира "deal" или "news"
    ещё ни разу не фиксировалось время последней публикации, выставляем
    его на "сейчас" вместо того, чтобы оставлять пустым.

    Без этого при самом первом запуске (или после переноса старого
    state.json без этого поля) первая же попавшаяся скидка и первая же
    попавшаяся новость публиковались бы сразу и одновременно — ведь
    сравнивать интервал было бы не с чем, и проверка "прошло ли
    достаточно времени" пропускалась. Тир "hot" не сеется — он и должен
    быть мгновенным всегда, это не баг, а расчётное поведение.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    last_published = data.setdefault("last_published", {})
    for tier in ("deal", "news"):
        if tier not in last_published:
            last_published[tier] = now_iso


def load_state() -> dict:
    if not os.path.exists(STATE_PATH):
        data = {k: (v.copy() if isinstance(v, (list, dict)) else v) for k, v in DEFAULT_STATE.items()}
        _seed_last_published(data)
        return data

    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[state] Не удалось прочитать state.json ({e}), начинаю с чистого состояния")
        data = {}

    for key, default in DEFAULT_STATE.items():
        if key not in data:
            data[key] = default.copy() if isinstance(default, (list, dict)) else default

    _seed_last_published(data)
    return data


def save_state(state: dict) -> None:
    trimmed = {
        "posted_deals": list(state.get("posted_deals", []))[-MAX_POSTED_ITEMS:],
        "posted_news": list(state.get("posted_news", []))[-MAX_POSTED_ITEMS:],
        "queue": list(state.get("queue", [])),
        "queued_ids": list(state.get("queued_ids", [])),
        "last_published": dict(state.get("last_published", {})),
        "known_game_titles": list(state.get("known_game_titles", []))[-MAX_KNOWN_TITLES:],
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)


def remember_game_title(state: dict, title: str) -> None:
    """Добавляет название игры в список известных (используется при переводе новостей)."""
    if not title:
        return
    titles = state.setdefault("known_game_titles", [])
    if title not in titles:
        titles.append(title)
