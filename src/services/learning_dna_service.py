from collections import Counter

from src.skills.skill_graph import get_skill


SERVICE_SKILL_NAMES = {
    "general_learning": "Общий прогресс обучения",
}

TREND_NAMES = {
    "up": "растёт",
    "down": "снижается",
    "stable": "стабильный",
    "uncertain": "неустойчивый",
    "unknown": "пока не определён",
}


def _skill_name(skill_id: str) -> str:
    if skill_id in SERVICE_SKILL_NAMES:
        return SERVICE_SKILL_NAMES[skill_id]
    skill = get_skill(skill_id)
    return skill["name"] if skill else "Неизвестный навык"


def _trend_name(trend: str) -> str:
    return TREND_NAMES.get(trend, "пока не определён")


def _topic_counts(signals: list[dict], signal_type: str) -> Counter:
    return Counter(
        signal.get("topic") or "Тема не указана"
        for signal in signals
        if signal.get("type") == signal_type
    )


def _format_topic_counts(counts: Counter) -> str:
    if not counts:
        return "нет данных"
    return ", ".join(
        f"{topic} ({count})"
        for topic, count in counts.most_common(3)
    )


def format_learning_dna_for_teacher(dna: dict) -> str:
    signals = dna.get("signals") or []
    successes = _topic_counts(signals, "success")
    mistakes = _topic_counts(signals, "mistake")
    unclear_count = sum(
        signal.get("type") == "unclear" for signal in signals
    )
    trajectory = dna.get("trajectory") or {}
    recommendations = trajectory.get("recommendations") or []
    skills = dna.get("skills") or {}

    skill_lines = []
    for skill_id, skill in sorted(skills.items()):
        skill_lines.append(
            f"• {_skill_name(skill_id)}: "
            f"уровень {skill.get('skill_level', 0)}, "
            f"попыток {skill.get('attempts', 0)}, "
            f"тренд {_trend_name(skill.get('trend', 'unknown'))}"
        )
    skills_text = "\n".join(skill_lines) or "• данных пока нет"

    recommendation = (
        recommendations[-1]
        if recommendations
        else "Сначала накопить ещё подтверждённые работы."
    )
    motivation = dna.get("motivation") or {}

    return (
        "🧬 ДНК знаний ученика\n\n"
        f"Telegram ID: {dna.get('student_id', '—')}\n"
        f"Подтверждённых сигналов: {len(signals)}\n"
        f"Успехи по темам: {_format_topic_counts(successes)}\n"
        f"Ошибки по темам: {_format_topic_counts(mistakes)}\n"
        f"Неясных проверок: {unclear_count}\n"
        f"XP: {motivation.get('xp', 0)}\n\n"
        "Навыки:\n"
        f"{skills_text}\n\n"
        f"🎯 Следующий фокус: "
        f"{trajectory.get('next_focus') or 'не определён'}\n"
        f"📌 Рекомендация: {recommendation}\n\n"
        f"Обновлено: {dna.get('updated_at', '—')}"
    )
