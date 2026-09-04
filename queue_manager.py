"""
Очередь публикаций с приоритетами.

Тиры (приоритеты), от высокого к низкому:
  hot   — очень крупная скидка (🔥) или бесплатная игра (🆓) — публикуется
          практически сразу (ограничено только небольшой паузой между
          сообщениями, чтобы не упереться в лимиты Telegram).
  deal  — обычная скидка (💰) — не чаще, чем раз в интервал для "deal".
  news  — обычная игровая новость (📰) — не чаще, чем раз в интервал для "news".

Все найденные новые материалы сначала попадают в очередь (state["queue"]),
а затем постепенно публикуются с учётом минимального интервала для
каждого тира. Так подписчики не получают "залп" из десяти сообщений
одновременно.

Каждая запись в очереди может объединять несколько "исходных" материалов
(member_ids) — это нужно для склеенных постов о распродаже издателя:
сама запись в очереди одна, но помечать как "опубликовано" нужно все
входящие в неё игры, чтобы они не попали в канал повторно по отдельности.
"""

from datetime import datetime, timezone

TIERS_PRIORITY = ["hot", "deal", "news"]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def enqueue(state: dict, item_id: str, tier: str, text: str,
            member_ids: list[str] | None = None) -> bool:
    """Добавляет материал в очередь, если его там ещё нет. Возвращает True, если добавили."""
    queued_ids = set(state.setdefault("queued_ids", []))
    if item_id in queued_ids:
        return False

    ids_to_mark = member_ids if member_ids else [item_id]

    state.setdefault("queue", []).append({
        "id": item_id,
        "tier": tier,
        "text": text,
        "member_ids": ids_to_mark,
        "added_at": to_iso(now_utc()),
    })

    queued_ids.add(item_id)
    queued_ids.update(ids_to_mark)
    state["queued_ids"] = list(queued_ids)
    return True


def _pop_next(state: dict, tier: str) -> dict | None:
    queue = state.setdefault("queue", [])
    for i, item in enumerate(queue):
        if item.get("tier") == tier:
            return queue.pop(i)
    return None


def _requeue_front(state: dict, item: dict) -> None:
    """Возвращает материал в начало очереди (например, если отправка не удалась)."""
    queue = state.setdefault("queue", [])
    queue.insert(0, item)


def _discard_from_queued_ids(state: dict, item: dict) -> None:
    queued_ids = set(state.get("queued_ids", []))
    queued_ids.discard(item["id"])
    for mid in item.get("member_ids", []):
        queued_ids.discard(mid)
    state["queued_ids"] = list(queued_ids)


def process_queue(state: dict, send_fn, tier_intervals: dict,
                   max_posts: int, delay_between_posts: float,
                   sleep_fn) -> int:
    """
    Публикует материалы из очереди, соблюдая минимальные интервалы между
    публикациями каждого тира. send_fn(item: dict) -> bool должен
    отправить сообщение (и сам разметить member_ids как опубликованные
    при успехе) и вернуть True/False.

    Возвращает количество успешно отправленных сообщений.
    """
    sent = 0
    last_published = state.setdefault("last_published", {})

    progressed = True
    while progressed and sent < max_posts:
        progressed = False
        for tier in TIERS_PRIORITY:
            if sent >= max_posts:
                break

            interval = tier_intervals.get(tier, 0)
            last_dt = parse_iso(last_published.get(tier))
            now = now_utc()
            if last_dt is not None and (now - last_dt).total_seconds() < interval:
                continue  # для этого тира ещё рано

            item = _pop_next(state, tier)
            if item is None:
                continue  # в этом тире сейчас нечего публиковать

            ok = send_fn(item)
            if ok:
                last_published[tier] = to_iso(now_utc())
                _discard_from_queued_ids(state, item)
                sent += 1
                progressed = True
                if sent < max_posts:
                    sleep_fn(delay_between_posts)
            else:
                # Не получилось — вернём в очередь и попробуем в другой раз.
                _requeue_front(state, item)

    return sent
