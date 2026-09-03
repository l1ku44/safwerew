"""
Скидки GOG через их каталожный API (catalog.gog.com).
Ключи в ответе GOG периодически чуть меняются, поэтому здесь используется
"мягкий" разбор: код пробует несколько вариантов названия поля и не падает
целиком, если что-то не найдено — просто пропускает конкретную игру и
пишет об этом в лог (видно во вкладке Actions на GitHub).
"""

import requests

GOG_URL = "https://catalog.gog.com/v1/catalog"


def _first(d: dict, keys: list[str], default=None):
    for k in keys:
        if isinstance(d, dict) and d.get(k) is not None:
            return d[k]
    return default


def get_deals(country: str = "US", currency: str = "USD",
              min_discount: int = 50, limit: int = 15) -> list[dict]:
    """
    Возвращает список скидок GOG с процентом скидки >= min_discount.
    Каждый элемент: {id, title, discount, price, old_price, currency, url}
    """
    deals: list[dict] = []
    try:
        resp = requests.get(GOG_URL, params={
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

            final_price = _first(price_block, ["finalAmount", "final", "amount"])
            base_price = _first(price_block, ["baseAmount", "base"])

            slug = p.get("slug")
            if not slug:
                raw_url = p.get("url") or ""
                slug = raw_url.strip("/").split("/")[-1] if raw_url else None

            deals.append({
                "id": f"gog:{p.get('id')}",
                "title": p.get("title") or "Без названия",
                "discount": discount,
                "price": final_price,
                "old_price": base_price,
                "currency": currency,
                "url": f"https://www.gog.com/game/{slug}" if slug else "https://www.gog.com/games?discounted=true",
            })
        except Exception as e:
            print(f"[gog] Пропускаю игру из-за ошибки разбора ({p.get('title')}): {e}")
            continue

    deals.sort(key=lambda d: d["discount"], reverse=True)
    return deals[:limit]
