"""
Единый шаблон оформления постов: скидки, бесплатные игры, объединённые
распродажи одного издателя, новости.
"""

import html
from datetime import datetime

import currency

PLATFORM_META = {
    "steam": {"emoji": "⚙️", "name": "Steam"},
    "gog": {"emoji": "🕹", "name": "GOG"},
    "epic": {"emoji": "🎮", "name": "Epic Games"},
}

_MONTHS_RU_GENITIVE = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля", 5: "мая", 6: "июня",
    7: "июля", 8: "августа", 9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}


def _format_ru_date(iso_str: str | None) -> str | None:
    if not iso_str:
        return None
    try:
        cleaned = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        return f"{dt.day} {_MONTHS_RU_GENITIVE[dt.month]}"
    except (ValueError, KeyError):
        return None


def format_deal(item: dict, tier_emoji: str) -> str:
    meta = PLATFORM_META[item["platform"]]
    title = html.escape(item["title"])
    lines = [
        f"{meta['emoji']} {meta['name']}",
        f"{tier_emoji} Скидка {item['discount']}% на {title}",
        item["url"],
    ]
    lines.extend(currency.build_price_lines(item.get("prices", {})))
    return "\n".join(lines)


def format_free(item: dict, platform: str, end_date_iso: str | None = None) -> str:
    meta = PLATFORM_META[platform]
    title = html.escape(item["title"])
    ru_date = _format_ru_date(end_date_iso)
    header = f"🆓 Бесплатно до {ru_date} — {title}" if ru_date else f"🆓 Бесплатно — {title}"
    lines = [f"{meta['emoji']} {meta['name']}", header, item["url"]]
    return "\n".join(lines)


def format_bundle(platform: str, publisher: str, items: list[dict], tier_emoji: str,
                   max_games_listed: int = 25) -> str:
    meta = PLATFORM_META[platform]
    publisher_esc = html.escape(publisher)
    max_discount = max(i["discount"] for i in items)
    lines = [
        f"{tier_emoji} Большая распродажа в {meta['name']}",
        f"Скидки до {max_discount}% на игры издателя {publisher_esc}:",
    ]
    sorted_items = sorted(items, key=lambda i: i["discount"], reverse=True)
    for it in sorted_items[:max_games_listed]:
        lines.append(f"• {html.escape(it['title'])} — −{it['discount']}%")
    remainder = len(sorted_items) - max_games_listed
    if remainder > 0:
        lines.append(f"…и ещё {remainder} игр")
    return "\n".join(lines)


def format_news(item: dict) -> str:
    title = html.escape(item["title"])
    source = html.escape(item["source"])
    return f"📰 {title}\nИсточник: {source}\n{item['url']}"
