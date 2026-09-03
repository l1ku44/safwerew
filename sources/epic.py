"""
Epic Games Store не даёт официальный публичный API со списком ВСЕХ скидок,
поэтому мы используем их же собственный (неофициальный, но очень
стабильный и известный — на нём годами работают Discord-боты) эндпоинт
freeGamesPromotions. Он отдаёт игры, которые сейчас или скоро будут
раздаваться бесплатно — обычно это самая интересная новость для канала.
"""

import requests

EPIC_URL = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"


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
    Каждый элемент: {id, title, url}
    """
    games: list[dict] = []
    try:
        resp = requests.get(EPIC_URL, params={
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
            for group in offer_groups:
                for offer in group.get("promotionalOffers", []):
                    discount_pct = (offer.get("discountSetting") or {}).get("discountPercentage")
                    if discount_pct == 0:
                        is_free_now = True

            if not is_free_now:
                continue

            slug = _extract_slug(el)
            url = f"https://store.epicgames.com/{lang_prefix}/p/{slug}" if slug else "https://store.epicgames.com/"

            games.append({
                "id": f"epic:{el.get('id')}",
                "title": el.get("title") or "Без названия",
                "url": url,
            })
        except Exception as e:
            print(f"[epic] Пропускаю игру из-за ошибки разбора ({el.get('title')}): {e}")
            continue

    return games
