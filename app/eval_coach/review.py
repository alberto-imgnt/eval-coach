"""Spaced retrieval: when each completed lesson's questions come back, and in what order."""
from __future__ import annotations

INTERVAL_DAYS = (1, 3, 7)
DAY_SECONDS = 86400
MAX_PER_SITTING = 5


def key_of(lesson_id, item_id):
    return f"{lesson_id}:{item_id}"


def schedule(items, lesson_id, item_ids, now):
    """Every retrieval item of a completed lesson first comes due one day later."""
    for item_id in item_ids:
        items.setdefault(key_of(lesson_id, item_id), {
            "lesson": lesson_id, "item": item_id, "stage": 0,
            "due": now + INTERVAL_DAYS[0] * DAY_SECONDS, "retired": False,
        })


def is_due(entry, now):
    return not entry.get("retired") and entry.get("due") is not None and entry["due"] <= now


def due_keys(items, now):
    """Keys of the items due at this time, oldest first."""
    due = [key for key, entry in items.items() if is_due(entry, now)]
    due.sort(key=lambda key: (items[key]["due"], key))
    return due


def apply_answer(entry, correct, now):
    """Move an item forward through 1, 3 and 7 days and retire it, or back to 1 day if wrong."""
    if not correct:
        entry["stage"] = 0
        entry["due"] = now + INTERVAL_DAYS[0] * DAY_SECONDS
        entry["retired"] = False
        return entry
    stage = entry.get("stage", 0) + 1
    if stage >= len(INTERVAL_DAYS):
        entry["stage"] = len(INTERVAL_DAYS)
        entry["due"] = None
        entry["retired"] = True
    else:
        entry["stage"] = stage
        entry["due"] = now + INTERVAL_DAYS[stage] * DAY_SECONDS
    return entry


def pick_sitting(items, keys, limit=MAX_PER_SITTING):
    """Choose at most `limit` keys and mix them so adjacent items differ in lesson when possible."""
    groups = {}
    for key in keys:
        groups.setdefault(items[key]["lesson"], []).append(key)

    # Round-robin across lessons, so one large lesson cannot fill the sitting.
    chosen = {lesson: [] for lesson in groups}
    picked = 0
    while picked < limit and any(groups.values()):
        for lesson, queue in groups.items():
            if queue and picked < limit:
                chosen[lesson].append(queue.pop(0))
                picked += 1

    # Greedy: always take from the lesson with the most left, other than the last one used.
    order = []
    last = None
    while any(chosen.values()):
        candidates = [lesson for lesson, queue in chosen.items() if queue and lesson != last]
        if not candidates:
            candidates = [lesson for lesson, queue in chosen.items() if queue]
        lesson = max(candidates, key=lambda name: len(chosen[name]))
        order.append(chosen[lesson].pop(0))
        last = lesson
    return order
