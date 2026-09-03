"""
Новости об играх (в том числе анонсы новинок) из RSS-фидов игровых
изданий. RSS — открытый стандарт, такой источник не может "сломаться"
так же внезапно, как неофициальные API магазинов.

Список фидов и ключевые слова можно свободно менять ниже, без изменения
остального кода.
"""

import feedparser

# (Название источника для подписи в посте, ссылка на RSS-фид)
FEEDS = [
    ("Rock Paper Shotgun", "https://www.rockpapershotgun.com/feed/"),
    ("PC Gamer", "https://www.pcgamer.com/rss/"),
    ("PCGamesN", "https://www.pcgamesn.com/mainrss.xml"),
]

# Если список пуст — публикуются вообще все новости из фидов выше.
# Если что-то добавить (например ["announce", "release date", "trailer"]),
# в канал будут попадать только новости, в заголовке которых встречается
# хотя бы одно из этих слов (без учёта регистра).
REQUIRED_KEYWORDS: list[str] = []


def get_news(limit_per_feed: int = 5) -> list[dict]:
    """
    Возвращает свежие новости из всех фидов.
    Каждый элемент: {id, title, source, url}
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
            title = entry.get("title") or "Без названия"
            link = entry.get("link") or ""
            if not link:
                continue

            if REQUIRED_KEYWORDS:
                lowered = title.lower()
                if not any(kw.lower() in lowered for kw in REQUIRED_KEYWORDS):
                    continue

            items.append({
                "id": f"news:{link}",
                "title": title,
                "source": source_name,
                "url": link,
            })

    return items
