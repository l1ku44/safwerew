"""
Перевод текста новостей на русский язык, с попыткой не трогать названия
игр, компаний и людей (латиницей).

Как это работает:
1. В тексте ищутся "защищённые" куски — как из фиксированного списка
   игровых терминов (Steam, DLC, Early Access и т.д.), так и из списка
   уже известных боту точных названий игр (из скидок Steam/Epic/GOG —
   их-то мы знаем совершенно точно, в отличие от произвольного текста
   новости).
2. Эти куски на время перевода заменяются на служебные токены, которые
   переводчик не трогает.
3. Текст переводится на русский.
4. Токены заменяются обратно на исходные названия.

Это не идеальное решение (полноценное распознавание имён собственных —
отдельная сложная задача), но оно надёжно защищает главное: конкретные
названия игр, которые бот уже видел, и стандартные игровые термины.
Если в канале всё же проскочит переведённое название — можно добавить
его в EXTRA_PROTECTED_TERMS ниже.
"""

import re

try:
    from deep_translator import GoogleTranslator
    _TRANSLATOR_AVAILABLE = True
except Exception as e:  # библиотека может быть недоступна/сломана — не роняем весь бот
    print(f"[translate] Модуль перевода недоступен: {e}")
    _TRANSLATOR_AVAILABLE = False

# Термины, которые никогда не переводим (устоявшиеся игровые термины и названия платформ).
EXTRA_PROTECTED_TERMS = [
    "Epic Games Store", "Epic Games", "Steam Deck", "Steam",
    "GOG", "PlayStation Store", "PlayStation", "Xbox Game Pass",
    "Xbox", "Nintendo Switch", "Nintendo", "Game Pass",
    "DLC", "Early Access", "Season Pass", "Battle Pass",
    "Remastered", "Remake", "Definitive Edition", "Director's Cut",
    "Beta", "Alpha", "NPC", "PvP", "PvE", "RPG", "FPS", "MMO", "MMORPG", "AAA",
]


def _protected_terms(extra_protected: list[str] | None) -> list[str]:
    terms = list(EXTRA_PROTECTED_TERMS)
    if extra_protected:
        for t in extra_protected:
            t = (t or "").strip()
            if t and t not in terms:
                terms.append(t)
    # Длинные термины подставляем первыми, чтобы не разрезать более длинное совпадение
    terms.sort(key=len, reverse=True)
    return terms


def to_russian(text: str, extra_protected: list[str] | None = None) -> str:
    """
    Переводит текст на русский. Если перевод недоступен или произошла
    ошибка — возвращает исходный текст без изменений (лучше опубликовать
    новость на английском, чем не опубликовать вовсе).
    """
    if not text:
        return text
    if not _TRANSLATOR_AVAILABLE:
        return text

    terms = _protected_terms(extra_protected)
    placeholder_map = {}
    working_text = text

    for i, term in enumerate(terms):
        if term in working_text:
            token = f"XXKEEPXX{i}XXKEEPXX"
            placeholder_map[token] = term
            working_text = working_text.replace(term, token)

    try:
        translated = GoogleTranslator(source="auto", target="ru").translate(working_text)
    except Exception as e:
        print(f"[translate] Ошибка перевода, публикую оригинал на английском: {e}")
        return text

    if not translated:
        return text

    for token, term in placeholder_map.items():
        translated = re.sub(re.escape(token), term, translated, flags=re.IGNORECASE)

    return translated
