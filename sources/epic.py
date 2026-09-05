"""
Epic Games Store.

get_free_games() — бесплатные игры недели. Использует официальный (хоть
и неофициальный по документации) эндпоинт freeGamesPromotions — он много
лет стабильно работает и НЕ менялся в этом обновлении.

get_discounts() / get_multi_currency() — НОВОЕ: обычные %-скидки Epic
Games Store. Это САМАЯ рискованная часть проекта: у Epic нет официального
публичного API для получения списка скидок (в отличие от freeGamesPromotions,
который отдаёт именно только "бесплатные игры"). Здесь используется
сторонняя, но активно поддерживаемая библиотека epicstore_api, которая
берёт на себя обход защиты от ботов (Cloudflare) — писать эти запросы
вручную было бы значительно менее надёжно.

Если что-то в этой части сломается — остальной бот (Steam, GOG, бесплатные
игры Epic, новости) продолжит работать как обычно: все ошибки здесь
перехватываются и не "падают" наружу.
"""

import time
import requests

FREE_GAMES_URL = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"

try:
    from epicstore_api import EpicGamesStoreAPI
    _EPICSTORE_API_AVAILABLE = True
except Exception as e:
    print(f"[epic] Библиотека epicstore_api недоступна, скидки Epic Games собираться не будут: {e}")
    _EPICSTORE_API_AVAILABLE = False

# Код страны Epic Games для каждой валюты канала.
CURRENCY_EPIC_CC = {
    "USD": "US",
    "RUB": "RU",
    "KZT": "KZ",
    "UAH": "UA",
    "BYN": "BY",
}


def _extract_slug(element: dict) -> str | None:
    slug = element.get("productSlug") or element.get("urlSlug")
    if slug and slug != "[]":
        return slug

    mappings = ((element.get("catalogNs") or {}).get("mappings")) or []
    if mappings:
        return mappings[0].get("pageSlug")

    offer_mappings = element.get("offerMappings") or []
    if offer_mappings:
        return offer_mappings[0].get("pageSlug")

    return None


def get_free_games(locale: str = "en-US", country: str = "US") -> list[dict]:
    """
    Возвращает список игр, которые СЕЙЧАС бесплатны в Epic Games Store.
    Каждый элемент: {id, title, url, end_date}
    (эта функция не менялась в этом обновлении — она уже работала).
    """
    games: list[dict] = []
    try:
        resp = requests.get(FREE_GAMES_URL, params={
            "locale": locale,
            "country": country,
            "allowCountries": country,
        }, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[epic] Не удалось получить данные: {e}")
        return games

    try:
        elements = data["data"]["Catalog"]["searchStore"]["elements"]
    except (KeyError, TypeError) as e:
        print(f"[epic] Неожиданный формат ответа Epic: {e}")
        return games

    lang_prefix = locale.split("-")[0]

    for el in elements:
        try:
            offer_groups = ((el.get("promotions") or {}).get("promotionalOffers")) or []
            is_free_now = False
            end_date = None
            for group in offer_groups:
                for offer in group.get("promotionalOffers", []):
                    discount_pct = (offer.get("discountSetting") or {}).get("discountPercentage")
                    if discount_pct == 0:
                        is_free_now = True
                        end_date = offer.get("endDate")

            if not is_free_now:
                continue

            slug = _extract_slug(el)
            url = f"https://store.epicgames.com/{lang_prefix}/p/{slug}" if slug else "https://store.epicgames.com/"

            games.append({
                "id": f"epic:{el.get('id')}",
                "title": el.get("title") or "Без названия",
                "url": url,
                "end_date": end_date,
            })
        except Exception as e:
            print(f"[epic] Пропускаю игру из-за ошибки разбора ({el.get('title')}): {e}")
            continue

    return games


def _extract_elements(result: dict) -> list:
    try:
        return result["data"]["Catalog"]["searchStore"]["elements"]
    except (KeyError, TypeError):
        return []


def _extract_price(element: dict, expected_currency: str | None = None):
    """Возвращает (current, original) в виде float, либо None если цены нет."""
    price = element.get("price") or {}
    total = price.get("totalPrice") or {}
    if not total:
        return None

    discount_price = total.get("discountPrice")
    original_price = total.get("originalPrice")
    if discount_price is None or original_price is None:
        return None

    decimals = ((total.get("currencyInfo") or {}).get("decimals"))
    if decimals is None:
        decimals = 2
    divisor = 10 ** decimals

    try:
        return (discount_price / divisor, original_price / divisor)
    except (TypeError, ZeroDivisionError):
        return None


def get_discounts(min_discount: int = 50, count: int = 50) -> list[dict]:
    """
    Возвращает список обычных %-скидок Epic Games Store (не путать с
    еженедельной бесплатной игрой — той занимается get_free_games).
    Каждый элемент: {id, raw_id, title, discount, url}
    """
    deals: list[dict] = []
    if not _EPICSTORE_API_AVAILABLE:
        return deals

    try:
        api = EpicGamesStoreAPI(country="US")
        result = api.fetch_store_games(count=count, with_price=True, allow_countries="US")
        elements = _extract_elements(result)
    except Exception as e:
        print(f"[epic] Не удалось получить список скидок: {e}")
        return deals

    for el in elements:
        try:
            price_info = _extract_price(el)
            if not price_info:
                continue
            current, original = price_info
            if not original or original <= 0 or current is None:
                continue
            if current <= 0:
                continue  # это бесплатная игра — ей занимается get_free_games
            discount = round((1 - current / original) * 100)
            if discount < min_discount:
                continue

            end_date = None
            offer_groups = ((el.get("promotions") or {}).get("promotionalOffers")) or []
            for group in offer_groups:
                for offer in group.get("promotionalOffers", []):
                    if offer.get("endDate"):
                        end_date = offer.get("endDate")

            slug = _extract_slug(el)
            deals.append({
                "id": f"epic:{el.get('id')}",
                "raw_id": el.get("id"),
                "title": el.get("title") or "Без названия",
                "discount": discount,
                "url": f"https://store.epicgames.com/en/p/{slug}" if slug else "https://store.epicgames.com/",
                "end_date": end_date,
            })
        except Exception as e:
            print(f"[epic] Пропускаю игру из-за ошибки разбора: {e}")
            continue

    return deals


def get_multi_currency(title: str, raw_id: str | None,
                        currencies=("USD", "RUB", "KZT", "UAH", "BYN"),
                        delay: float = 0.3) -> dict:
    """
    "Best effort": ищет ту же игру в сторе по названию отдельно для каждого
    региона и берёт оттуда цену. Это самый ненадёжный участок проекта —
    если для какой-то валюты игра не находится или цена не распознаётся,
    эта валюта просто пропускается.
    """
    prices = {}
    if not _EPICSTORE_API_AVAILABLE or not title:
        return prices

    for code in currencies:
        cc = CURRENCY_EPIC_CC.get(code)
        if not cc:
            continue
        try:
            api = EpicGamesStoreAPI(country=cc)
            result = api.fetch_store_games(count=10, keywords=title, with_price=True, allow_countries=cc)
            elements = _extract_elements(result)

            match = None
            if raw_id:
                match = next((e for e in elements if e.get("id") == raw_id), None)
            if match is None:
                match = next(
                    (e for e in elements if (e.get("title") or "").strip().lower() == title.strip().lower()),
                    None,
                )
            if match is None:
                continue

            price_info = _extract_price(match)
            if not price_info:
                continue
            current, original = price_info
            prices[code] = {"current": current, "original": original}
        except Exception as e:
            print(f"[epic] Не удалось получить цену «{title}» в {code}: {e}")
        time.sleep(delay)

    return prices
