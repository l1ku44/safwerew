"""
Скидки GOG.

get_deals() — определяет, КАКИЕ игры сейчас со скидкой, через каталожный
API (catalog.gog.com). Базовая, проверенная логика, не менялась.

get_multi_currency() — НОВОЕ и менее надёжное: пытается получить цену
конкретной игры в нескольких валютах через api.gog.com/products/{id}/prices.
У GOG нет официальной документации на этот эндпоинт, и по отзывам
сообщества разработчиков он не всегда стабилен — поэтому код здесь
особенно "мягкий": при любой проблеме с конкретной валютой она просто
пропускается, а не ломает всю публикацию. Известный факт: у GOG почти
наверняка нет отдельных цен в KZT и BYN (такие сторфронты не значатся
в списке поддерживаемых), так что для этих валют пустой результат — это
норма, а не баг.
"""

import time
import requests

GOG_CATALOG_URL = "https://catalog.gog.com/v1/catalog"
GOG_PRICE_URL = "https://api.gog.com/products/{id}/prices"

# Код страны GOG для каждой валюты канала (KZT/BYN, скорее всего, не поддерживаются GOG).
CURRENCY_GOG_CC = {
    "USD": "US",
    "RUB": "RU",
    "KZT": "KZ",
    "UAH": "UA",
    "BYN": "BY",
}


def _first(d: dict, keys: list[str], default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return default


def _to_float(raw):
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def get_deals(country: str = "US", currency: str = "USD",
              min_discount: int = 50, limit: int = 30) -> list[dict]:
    """
    Возвращает список скидок GOG с процентом скидки >= min_discount.
    Каждый элемент: {id, price_id, title, discount, price, old_price,
    currency, url, publisher}
    """
    deals: list[dict] = []
    try:
        resp = requests.get(GOG_CATALOG_URL, params={
            "price": "discounted",
            "order": "desc:discount",
            "limit": 48,
            "countryCode": country,
            "currencyCode": currency,
        }, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[gog] Не удалось получить данные: {e}")
        return deals

    products = data.get("products") or []

    for p in products:
        try:
            price_block = p.get("price") or {}
            discount = _first(price_block, ["discountPercentage", "discount"], 0)
            discount = int(discount or 0)
            if discount < min_discount:
                continue

            final_price = _to_float(_first(price_block, ["finalAmount", "final", "amount"]))
            base_price = _to_float(_first(price_block, ["baseAmount", "base"]))

            slug = p.get("slug")
            if not slug:
                raw_url = p.get("url") or ""
                slug = raw_url.strip("/").split("/")[-1] if raw_url else None

            # Для мультивалютного запроса ценам нужен "классический" числовой ID GOG.
            price_id = p.get("externalProductId") or p.get("id")

            publisher = None
            pub_field = p.get("publisher") or p.get("developer")
            if isinstance(pub_field, dict):
                publisher = pub_field.get("name")
            elif isinstance(pub_field, str):
                publisher = pub_field

            deals.append({
                "id": f"gog:{p.get('id')}",
                "price_id": price_id,
                "title": p.get("title") or "Без названия",
                "discount": discount,
                "price": final_price,
                "old_price": base_price,
                "currency": currency,
                "url": f"https://www.gog.com/game/{slug}" if slug else "https://www.gog.com/games?discounted=true",
                "publisher": publisher,
            })
        except Exception as e:
            print(f"[gog] Пропускаю игру из-за ошибки разбора ({p.get('title')}): {e}")
            continue

    deals.sort(key=lambda d: d["discount"], reverse=True)
    return deals[:limit]


def _first_price_entry(data):
    """Формат ответа api.gog.com/products/{id}/prices точно не задокументирован,
    поэтому пробуем несколько правдоподобных вариантов структуры."""
    if isinstance(data, list) and data:
        return data[0]
    if isinstance(data, dict):
        embedded = data.get("_embedded") or {}
        prices_list = embedded.get("prices")
        if isinstance(prices_list, list) and prices_list:
            return prices_list[0]
        if isinstance(data.get("prices"), list) and data["prices"]:
            return data["prices"][0]
        return data
    return None


def get_multi_currency(price_id, currencies=("USD", "RUB", "KZT", "UAH", "BYN"),
                        delay: float = 0.3) -> dict:
    """
    "Best effort" получение цены в нескольких валютах. Возвращает только
    те валюты, для которых удалось получить и распознать цену.
    """
    prices = {}
    if not price_id:
        return prices

    for code in currencies:
        cc = CURRENCY_GOG_CC.get(code)
        if not cc:
            continue
        try:
            resp = requests.get(GOG_PRICE_URL.format(id=price_id),
                                 params={"countryCode": cc}, timeout=15)
            if resp.status_code != 200:
                continue
            data = resp.json()
            entry = _first_price_entry(data)
            if not entry:
                continue
            current = _to_float(_first(entry, ["finalPrice", "final_price", "final", "amount"]))
            original = _to_float(_first(entry, ["basePrice", "base_price", "base"]))
            if current is None or original is None:
                continue
            prices[code] = {"current": current, "original": original}
        except Exception as e:
            print(f"[gog] Не удалось получить цену {price_id} в {code}: {e}")
        time.sleep(delay)

    return prices
