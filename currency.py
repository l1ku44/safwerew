"""
Форматирование цен в нескольких валютах с флагами и символами.

Формат строго по образцу:
  🇺🇸 $11.99 → $59.99
  🇷🇺 1 199 ₽ → 3 599 ₽
  🇰🇿 5 999 ₸ → 29 999 ₸
  🇺🇦 499 ₴ → 1 499 ₴
  🇧🇾 39.99 Br → 119.99 Br

Порядок: сначала текущая (со скидкой) цена, потом обычная (полная).
Если для какой-то валюты цены нет — строка просто не добавляется.
"""

# Порядок вывода валют в посте — фиксированный.
CURRENCY_ORDER = ["USD", "RUB", "KZT", "UAH", "BYN"]

FLAGS = {
    "USD": "🇺🇸",
    "RUB": "🇷🇺",
    "KZT": "🇰🇿",
    "UAH": "🇺🇦",
    "BYN": "🇧🇾",
}

# decimals: сколько знаков после запятой показывать
# symbol_after: символ ставится после числа (через пробел) или перед (без пробела)
_CURRENCY_META = {
    "USD": {"symbol": "$", "decimals": 2, "symbol_after": False},
    "RUB": {"symbol": "₽", "decimals": 0, "symbol_after": True},
    "KZT": {"symbol": "₸", "decimals": 0, "symbol_after": True},
    "UAH": {"symbol": "₴", "decimals": 0, "symbol_after": True},
    "BYN": {"symbol": "Br", "decimals": 2, "symbol_after": True},
}


def format_amount(value: float, code: str) -> str:
    meta = _CURRENCY_META[code]
    decimals = meta["decimals"]
    # Пробел как разделитель тысяч (кроме USD, там привычнее запятая)
    if code == "USD":
        number = f"{value:,.{decimals}f}"
    else:
        number = f"{value:,.{decimals}f}".replace(",", " ")

    if meta["symbol_after"]:
        return f"{number} {meta['symbol']}"
    return f"{meta['symbol']}{number}"


def build_price_lines(prices: dict) -> list[str]:
    """
    prices: {"USD": {"current": 11.99, "original": 59.99}, "RUB": {...}, ...}
    Валюты, которых нет в словаре (или где current/original отсутствуют),
    просто пропускаются — как и требуется.

    Порядок: сначала старая (зачёркнутая) цена, потом текущая со скидкой —
    "было → стало". HTML-тег <s> — зачёркивание, корректно отображается
    в Telegram, так как сообщения отправляются с parse_mode="HTML".
    """
    lines = []
    for code in CURRENCY_ORDER:
        p = prices.get(code)
        if not p:
            continue
        current = p.get("current")
        original = p.get("original")
        if current is None or original is None:
            continue
        try:
            current_str = format_amount(float(current), code)
            original_str = format_amount(float(original), code)
        except (TypeError, ValueError):
            continue
        lines.append(f"{FLAGS[code]} <s>{original_str}</s> → {current_str}")
    return lines
