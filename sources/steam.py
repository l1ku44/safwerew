"""
Скидки Steam через официальный (хоть и недокументированный) API магазина.
Этот эндпоинт много лет используется тысячами ботов и сайтов, так что
он один из самых надёжных источников в этом проекте.
"""

import requests

STEAM_URL = "https://store.steampowered.com/api/featuredcategories/"


def get_deals(country: str = "us", lang: str = "english",
              min_discount: int = 50, limit: int = 15) -> list[dict]:
    """
    Возвращает список скидок Steam с процентом скидки >= min_discount.
    Каждый элемент: {id, title, discount, price, old_price, currency, url}
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
