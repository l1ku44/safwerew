"""
Новости об играх (в том числе анонсы новинок) из RSS-фидов игровых
изданий, переведённые на русский язык.

Список фидов и ключевые слова можно свободно менять ниже, без изменения
остального кода.
"""

import feedparser
import translate

# (Название источника для подписи в посте, ссылка на RSS-фид)
FEEDS = [
    ("Rock Paper Shotgun", "https://www.rockpapershotgun.com/feed/"),
    ("PC Gamer", "https://www.pcgamer.com/rss/"),
    ("PCGamesN", "https://www.pcgamesn.com/mainrss.xml"),
]

# Если список пуст — публикуются вообще все новости из фидов выше.
# Если что-то добавить (например ["announce", "release date", "trailer"]),
# в канал будут попадать только новости, в заголовке которых встречается
# хотя бы одно из этих слов (без учёта регистра). Фильтр применяется к
# ОРИГИНАЛЬНОМУ (английскому) заголовку, до перевода.
REQUIRED_KEYWORDS: list[str] = []


def get_news(limit_per_feed: int = 5, protected_terms: list[str] | None = None) -> list[dict]:
    """
    Возвращает свежие новости из всех фидов, с заголовком, переведённым
    на русский. Каждый элемент: {id, title, title_original, source, url}
    """
    items: list[dict] = []

    for source_name, feed_url in FEEDS:
        try:
            parsed = feedparser.parse(feed_url)
        except Exception as e:
            print(f"[news] Ошибка загрузки фида {source_name}: {e}")
            continue

        if parsed.bozo and not parsed.entries:
            print(f"[news] Не удалось разобрать фид {source_name}: {parsed.get('bozo_exception')}")
            continue

        for entry in parsed.entries[:limit_per_feed]:
            title_original = entry.get("title") or "Без названия"
            link = entry.get("link") or ""
            if not link:
                continue

            if REQUIRED_KEYWORDS:
                lowered = title_original.lower()
                if not any(kw.lower() in lowered for kw in REQUIRED_KEYWORDS):
                    continue

            title_ru = translate.to_russian(title_original, extra_protected=protected_terms)

            items.append({
                "id": f"news:{link}",
                "title": title_ru,
                "title_original": title_original,
                "source": source_name,
                "url": link,
            })

    return items
