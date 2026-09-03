"""
Главный скрипт бота.

Что делает при каждом запуске:
  1. Проверяет скидки в Steam и GOG, бесплатные игры в Epic Games Store,
     свежие новости из игровых RSS-фидов.
  2. Сравнивает найденное со списком уже опубликованного (state.json).
  3. Публикует в Telegram-канал только то, чего ещё не было.
  4. Сохраняет обновлённый список опубликованного.

Запускается по расписанию через GitHub Actions (см. .github/workflows/bot.yml).
"""

import html
import time

from state import load_state, save_state
from telegram_client import send_message
from sources import steam, epic, gog, news

# ==================== НАСТРОЙКИ ====================
# Минимальный процент скидки, начиная с которого игра попадает в канал.
MIN_DISCOUNT_STEAM = 50
MIN_DISCOUNT_GOG = 50

# Регион и валюта для Steam / GOG. Примеры: ("us", "USD"), ("de", "EUR"), ("ru", "RUB").
STEAM_COUNTRY, STEAM_LANG = "us", "english"
GOG_COUNTRY, GOG_CURRENCY = "US", "USD"

# Сколько сообщений максимум отправлять за один запуск (защита от "спам-залпа",
# если бот не запускался долго и накопилось много нового). Остальное уйдёт
# в следующие запуски по расписанию.
MAX_POSTS_PER_RUN = 12

# Пауза между сообщениями в секундах (чтобы не упереться в лимиты Telegram).
DELAY_BETWEEN_POSTS = 2
# =====================================================


def format_deal(deal: dict, emoji: str) -> str:
    title = html.escape(deal["title"])
    lines = [f"{emoji} <b>{title}</b>"]

    discount = deal.get("discount")
    price = deal.get("price")
    old_price = deal.get("old_price")
    currency = deal.get("currency") or ""

    if discount is not None and price is not None:
        if old_price:
            lines.append(f"Скидка {discount}%: {price} {currency} (было {old_price} {currency})")
        else:
            lines.append(f"Скидка {discount}%: {price} {currency}")

    lines.append(deal["url"])
    return "\n".join(lines)


def format_free(deal: dict, emoji: str) -> str:
    title = html.escape(deal["title"])
    return f"{emoji} <b>{title}</b>\nСейчас бесплатно!\n{deal['url']}"


def format_news(item: dict) -> str:
    title = html.escape(item["title"])
    source = html.escape(item["source"])
    return f"📰 <b>{title}</b>\nИсточник: {source}\n{item['url']}"


def collect_new_items(state: dict) -> list[tuple[str, str, str]]:
    """Возвращает список (тип, id, текст_сообщения) для всего нового."""
    posted_deals = set(state.get("posted_deals", []))
    posted_news = set(state.get("posted_news", []))

    to_send: list[tuple[str, str, str]] = []

    for deal in steam.get_deals(country=STEAM_COUNTRY, lang=STEAM_LANG, min_discount=MIN_DISCOUNT_STEAM):
        if deal["id"] not in posted_deals:
            to_send.append(("deal", deal["id"], format_deal(deal, "🟦 Steam")))

    for deal in epic.get_free_games():
        if deal["id"] not in posted_deals:
            to_send.append(("deal", deal["id"], format_free(deal, "⬛️ Epic Games —")))

    for deal in gog.get_deals(country=GOG_COUNTRY, currency=GOG_CURRENCY, min_discount=MIN_DISCOUNT_GOG):
        if deal["id"] not in posted_deals:
            to_send.append(("deal", deal["id"], format_deal(deal, "🟪 GOG")))

    for item in news.get_news():
        if item["id"] not in posted_news:
            to_send.append(("news", item["id"], format_news(item)))

    return to_send


def main() -> None:
    state = load_state()
    posted_deals = set(state.get("posted_deals", []))
    posted_news = set(state.get("posted_news", []))

    to_send = collect_new_items(state)

    if not to_send:
        print("Новых записей нет — постить нечего.")
        return

    print(f"Найдено новых записей: {len(to_send)}")

    sent_count = 0
    for kind, item_id, text in to_send:
        if sent_count >= MAX_POSTS_PER_RUN:
            remaining = len(to_send) - sent_count
            print(f"Достигнут лимит {MAX_POSTS_PER_RUN} постов за запуск. "
                  f"Осталось {remaining} — уйдут в следующие запуски.")
            break

        ok = send_message(text)
        if ok:
            if kind == "deal":
                posted_deals.add(item_id)
            else:
                posted_news.add(item_id)
            sent_count += 1
            time.sleep(DELAY_BETWEEN_POSTS)
        else:
            print(f"Не удалось отправить (пропускаю, попробуем в следующий раз): {item_id}")

    state["posted_deals"] = list(posted_deals)
    state["posted_news"] = list(posted_news)
    save_state(state)

    print(f"Готово. Отправлено сообщений: {sent_count}")


if __name__ == "__main__":
    main()
