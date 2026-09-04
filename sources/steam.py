"""
Скидки Steam через официальный (хоть и недокументированный) API магазина.
Этот эндпоинт много лет используется тысячами ботов и сайтов, так что
он один из самых надёжных источников в этом проекте.

get_deals() — определяет, КАКИЕ игры сейчас со скидкой (базовая, проверенная
логика, не менялась).
get_multi_currency() — НОВОЕ: для конкретной игры получает цену в нескольких
валютах/регионах через appdetails (тоже официальный эндпоинт Steam,
используется так же широко, как и featuredcategories).
"""

import time
import requests

STEAM_URL = "https://store.steampowered.com/api/featuredcategories/"
APPDETAILS_URL = "https://store.steampowered.com/api/appdetails"

# Код страны Steam (cc) для каждой валюты канала.
CURRENCY_STEAM_CC = {
    "USD": "us",
    "RUB": "ru",
    "KZT": "kz",
    "UAH": "ua",
    "BYN": "by",
}


def get_deals(country: str = "us", lang: str = "english",
              min_discount: int = 50, limit: int = 30) -> list[dict]:
    """
    Возвращает список скидок Steam с процентом скидки >= min_discount.
    Каждый элемент: {id, title, discount, price, old_price, currency, url}
    (price/old_price/currency здесь — только для базовой валюты country,
    полную мультивалютную картину даёт get_multi_currency).
    """
    deals: list[dict] = []
    try:
        resp = requests.get(STEAM_URL, params={"cc": country, "l": lang}, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[steam] Не удалось получить данные: {e}")
        return deals

    items = (data.get("specials") or {}).get("items") or []

    for item in items:
        try:
            discount = int(item.get("discount_percent", 0) or 0)
            if discount < min_discount:
                continue

            appid = item.get("id")
            final_price = item.get("final_price")
            original_price = item.get("original_price")

            deals.append({
                "id": f"steam:{appid}",
                "appid": appid,
                "title": item.get("name") or "Без названия",
                "discount": discount,
                "price": round(final_price / 100, 2) if final_price is not None else None,
                "old_price": round(original_price / 100, 2) if original_price is not None else None,
                "currency": item.get("currency") or "",
                "url": f"https://store.steampowered.com/app/{appid}/" if appid else "https://store.steampowered.com/specials/",
            })
        except Exception as e:
            print(f"[steam] Пропускаю игру из-за ошибки разбора ({item.get('name')}): {e}")
            continue

    deals.sort(key=lambda d: d["discount"], reverse=True)
    return deals[:limit]


def get_multi_currency(appid, currencies=("USD", "RUB", "KZT", "UAH", "BYN"),
                        delay: float = 0.3) -> tuple[dict, str | None]:
    """
    Возвращает (prices, publisher) для конкретной игры.
    prices: {"USD": {"current": 11.99, "original": 59.99}, ...} — только
    те валюты, для которых удалось получить цену (например, если игра
    не продаётся в конкретном регионе — эта валюта просто отсутствует).
    publisher: имя издателя (для группировки похожих скидок), либо None.
    """
    prices = {}
    publisher = None

    for code in currencies:
        cc = CURRENCY_STEAM_CC.get(code)
        if not cc:
            continue
        try:
            resp = requests.get(APPDETAILS_URL, params={"appids": appid, "cc": cc, "l": "english"}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            entry = (data or {}).get(str(appid)) or {}
            if not entry.get("success"):
                continue
            app_data = entry.get("data") or {}

            if publisher is None:
                pubs = app_data.get("publishers") or []
                if pubs:
                    publisher = pubs[0]

            price_overview = app_data.get("price_overview")
            if not price_overview:
                continue
            initial = price_overview.get("initial")
            final = price_overview.get("final")
            if initial is None or final is None:
                continue

            prices[code] = {"current": final / 100, "original": initial / 100}
        except Exception as e:
            print(f"[steam] Не удалось получить цену appid={appid} в {code}: {e}")
        time.sleep(delay)

    return prices, publisher
