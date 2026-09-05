"""
Главный скрипт бота.

Что делает при каждом запуске (запускается часто, каждые несколько минут):
  1. Проверяет скидки в Steam, GOG и Epic Games Store, бесплатные игры в
     Epic Games Store, свежие новости из игровых RSS-фидов (переводит их
     на русский).
  2. Похожие скидки одного издателя (если их много одновременно) склеивает
     в один пост вместо потока одинаковых сообщений.
  3. Кладёт всё новое в очередь публикаций с приоритетом (см. queue_manager.py).
  4. Публикует из очереди то, для чего уже подошло время — так очень
     выгодные предложения выходят почти сразу, а обычные скидки и новости
     публикуются постепенно, не "заливая" подписчиков сразу пачкой постов.
  5. Сохраняет состояние (что опубликовано, что в очереди, когда что
     публиковали последний раз).
"""

import time
from collections import defaultdict

import formatting
import queue_manager
from state import load_state, save_state, remember_game_title
from telegram_client import send_message
from sources import steam, epic, gog, news

# ==================== НАСТРОЙКИ ====================

# Валюты, которые показываем в постах о скидках (порядок вывода — в currency.py).
CURRENCIES = ("USD", "RUB", "KZT", "UAH", "BYN")

# Минимальный процент скидки, начиная с которого игра вообще попадает в канал.
MIN_DISCOUNT_STEAM = 40
MIN_DISCOUNT_GOG = 40
MIN_DISCOUNT_EPIC = 40

# Скидки от этого процента считаются "горячими" (🔥) и публикуются
# практически сразу, а не по обычному расписанию тира "deal".
HOT_DISCOUNT_THRESHOLD = 70

# От скольких новых скидок ОДНОГО издателя на ОДНОЙ платформе за один
# запуск делать один общий пост вместо отдельного поста на каждую игру.
BUNDLE_MIN_COUNT = 4

# Минимальный интервал между публикациями одного тира, в секундах.
#   hot  — очень крупная скидка (🔥) или бесплатная игра (🆓)
#   deal — обычная скидка (💰): 10-15 минут
#   news — обычная игровая новость (📰): раз в сутки — канал в первую
#          очередь про скидки, новости не должны с ними конкурировать
TIER_INTERVAL_SECONDS = {
    "hot": 0,
    "deal": 12 * 60,
    "news": 24 * 60 * 60,
}

# Сколько сообщений максимум отправлять за один запуск (страховка на случай,
# если бот долго не запускался и в очереди накопилось много всего).
MAX_POSTS_PER_RUN = 10

# Пауза между отправками сообщений подряд, в секундах (чтобы не упереться
# в лимиты Telegram).
DELAY_BETWEEN_POSTS = 3
# =====================================================


def _tier_for_discount(discount: int) -> str:
    return "hot" if discount >= HOT_DISCOUNT_THRESHOLD else "deal"


def _already_seen(state: dict, item_id: str) -> bool:
    posted_list = state.get("posted_news", []) if item_id.startswith("news:") else state.get("posted_deals", [])
    if item_id in posted_list:
        return True
    if item_id in state.get("queued_ids", []):
        return True
    return False


def gather_deal_items(state: dict) -> list[dict]:
    """Собирает новые скидки со всех платформ вместе с ценами в нескольких
    валютах. Уже опубликованные или стоящие в очереди скидки повторно не
    запрашиваются (не тратим лишние запросы к API магазинов)."""
    raw_items: list[dict] = []

    # --- Steam ---
    try:
        steam_deals = steam.get_deals(min_discount=MIN_DISCOUNT_STEAM)
    except Exception as e:
        print(f"[main] Ошибка при получении скидок Steam: {e}")
        steam_deals = []
    for d in steam_deals:
        remember_game_title(state, d["title"])
    for d in steam_deals:
        if _already_seen(state, d["id"]):
            continue
        try:
            prices, publisher = steam.get_multi_currency(d["appid"], currencies=CURRENCIES)
        except Exception as e:
            print(f"[main] Ошибка при получении цен Steam для «{d['title']}»: {e}")
            prices, publisher = {}, None
        raw_items.append({
            "id": d["id"], "platform": "steam", "title": d["title"],
            "discount": d["discount"], "url": d["url"],
            "prices": prices, "publisher": publisher, "end_date": None,
        })

    # --- GOG ---
    try:
        gog_deals = gog.get_deals(min_discount=MIN_DISCOUNT_GOG)
    except Exception as e:
        print(f"[main] Ошибка при получении скидок GOG: {e}")
        gog_deals = []
    for d in gog_deals:
        remember_game_title(state, d["title"])
    for d in gog_deals:
        if _already_seen(state, d["id"]):
            continue
        try:
            prices = gog.get_multi_currency(d["price_id"], currencies=CURRENCIES)
        except Exception as e:
            print(f"[main] Ошибка при получении цен GOG для «{d['title']}»: {e}")
            prices = {}
        raw_items.append({
            "id": d["id"], "platform": "gog", "title": d["title"],
            "discount": d["discount"], "url": d["url"],
            "prices": prices, "publisher": d.get("publisher"), "end_date": None,
        })

    # --- Epic Games (обычные скидки, не еженедельная бесплатная игра) ---
    try:
        epic_deals = epic.get_discounts(min_discount=MIN_DISCOUNT_EPIC)
    except Exception as e:
        print(f"[main] Ошибка при получении скидок Epic Games: {e}")
        epic_deals = []
    for d in epic_deals:
        remember_game_title(state, d["title"])
    for d in epic_deals:
        if _already_seen(state, d["id"]):
            continue
        try:
            prices = epic.get_multi_currency(d["title"], d.get("raw_id"), currencies=CURRENCIES)
        except Exception as e:
            print(f"[main] Ошибка при получении цен Epic Games для «{d['title']}»: {e}")
            prices = {}
        raw_items.append({
            "id": d["id"], "platform": "epic", "title": d["title"],
            "discount": d["discount"], "url": d["url"],
            "prices": prices, "publisher": None, "end_date": d.get("end_date"),
        })

    return raw_items


def bundle_and_classify(raw_items: list[dict]) -> list[dict]:
    """Группирует похожие скидки одного издателя в один пост, остальное —
    по отдельности. Возвращает список готовых к очереди записей:
    {id, tier, text, member_ids}."""
    groups = defaultdict(list)
    singles = []

    for it in raw_items:
        publisher = it.get("publisher")
        if publisher:
            groups[(it["platform"], publisher)].append(it)
        else:
            singles.append(it)

    queue_items = []

    for (platform, publisher), items in groups.items():
        if len(items) >= BUNDLE_MIN_COUNT:
            max_discount = max(i["discount"] for i in items)
            tier = _tier_for_discount(max_discount)
            tier_emoji = "🔥" if tier == "hot" else "💰"
            text = formatting.format_bundle(platform, publisher, items, tier_emoji)
            member_ids = [i["id"] for i in items]
            bundle_id = "bundle:" + platform + ":" + publisher + ":" + "-".join(sorted(member_ids))
            queue_items.append({"id": bundle_id, "tier": tier, "text": text, "member_ids": member_ids})
        else:
            singles.extend(items)

    for it in singles:
        tier = _tier_for_discount(it["discount"])
        tier_emoji = "🔥" if tier == "hot" else "💰"
        text = formatting.format_deal(it, tier_emoji, end_date_iso=it.get("end_date"))
        queue_items.append({"id": it["id"], "tier": tier, "text": text, "member_ids": [it["id"]]})

    return queue_items


def gather_free_games(state: dict) -> list[dict]:
    try:
        free_games = epic.get_free_games()
    except Exception as e:
        print(f"[main] Ошибка при получении бесплатных игр Epic Games: {e}")
        free_games = []

    queue_items = []
    for g in free_games:
        if _already_seen(state, g["id"]):
            continue
        text = formatting.format_free(g, "epic", end_date_iso=g.get("end_date"))
        queue_items.append({"id": g["id"], "tier": "hot", "text": text, "member_ids": [g["id"]]})
    return queue_items


def gather_news_items(state: dict) -> list[dict]:
    try:
        items = news.get_news(protected_terms=state.get("known_game_titles", []))
    except Exception as e:
        print(f"[main] Ошибка при получении новостей: {e}")
        items = []

    queue_items = []
    for it in items:
        if _already_seen(state, it["id"]):
            continue
        text = formatting.format_news(it)
        queue_items.append({"id": it["id"], "tier": "news", "text": text, "member_ids": [it["id"]]})
    return queue_items


def make_send_fn(state: dict):
    def send_fn(item: dict) -> bool:
        ok = send_message(item["text"])
        if ok:
            member_ids = item.get("member_ids") or [item["id"]]
            posted_deals = set(state.get("posted_deals", []))
            posted_news = set(state.get("posted_news", []))
            for mid in member_ids:
                if mid.startswith("news:"):
                    posted_news.add(mid)
                else:
                    posted_deals.add(mid)
            state["posted_deals"] = list(posted_deals)
            state["posted_news"] = list(posted_news)
        return ok
    return send_fn


def main() -> None:
    state = load_state()

    new_queue_items = []
    new_queue_items.extend(bundle_and_classify(gather_deal_items(state)))
    new_queue_items.extend(gather_free_games(state))
    # Новости собираем последними: к этому моменту known_game_titles уже
    # пополнился названиями из свежих скидок этого запуска — это помогает
    # переводчику не трогать названия игр в новостных заголовках.
    new_queue_items.extend(gather_news_items(state))

    added = 0
    for qi in new_queue_items:
        if queue_manager.enqueue(state, qi["id"], qi["tier"], qi["text"], member_ids=qi["member_ids"]):
            added += 1

    if added:
        print(f"В очередь добавлено новых записей: {added}")
    else:
        print("Новых записей не найдено.")

    sent = queue_manager.process_queue(
        state,
        send_fn=make_send_fn(state),
        tier_intervals=TIER_INTERVAL_SECONDS,
        max_posts=MAX_POSTS_PER_RUN,
        delay_between_posts=DELAY_BETWEEN_POSTS,
        sleep_fn=time.sleep,
    )

    queue_len = len(state.get("queue", []))
    print(f"Опубликовано за этот запуск: {sent}. В очереди осталось: {queue_len}.")

    save_state(state)


if __name__ == "__main__":
    main()
