"""Deterministic topic progression for the informatics MVP."""


TOPIC_SEQUENCE = (
    "Системы счисления",
    "Арифметические операции в системах счисления",
    "Кодирование информации",
    "Основы логики",
    "Алгоритмы и исполнители",
    "Условные операторы",
    "Циклы",
)


def select_next_topic(completed_topic: str, topic_mastery: dict | None = None) -> str | None:
    """Return the first not-yet-mastered topic after ``completed_topic``.

    Unknown topics and the end of the current MVP sequence deliberately return
    ``None`` so a teacher remains in control instead of receiving a guessed topic.
    """
    try:
        start_index = TOPIC_SEQUENCE.index(completed_topic) + 1
    except ValueError:
        return None

    mastery = topic_mastery or {}
    for topic in TOPIC_SEQUENCE[start_index:]:
        if not (mastery.get(topic) or {}).get("mastered", False):
            return topic
    return None
