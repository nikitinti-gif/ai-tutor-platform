"""Deterministic topic progression for the informatics MVP."""

from src.skills.skill_graph import (
    get_skill_name,
    migrate_legacy_focus,
    select_next_skill,
)


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


def migrate_trajectory_to_skill_graph(dna: dict) -> bool:
    """Add atomic skill ids without discarding legacy topic history."""
    changed = False
    trajectory = dna.setdefault("trajectory", {})
    focus = trajectory.get("next_focus_skill_id") or trajectory.get("next_focus")
    migrated_focus = migrate_legacy_focus(focus)
    if migrated_focus and trajectory.get("next_focus_skill_id") != migrated_focus:
        trajectory["next_focus_skill_id"] = migrated_focus
        if not trajectory.get("next_focus"):
            trajectory["next_focus"] = get_skill_name(migrated_focus)
        changed = True

    skill_states = dna.setdefault("skills", {})
    for legacy_topic, mastery in (dna.get("topic_mastery") or {}).items():
        skill_id = migrate_legacy_focus(legacy_topic)
        if not skill_id or not isinstance(mastery, dict):
            continue
        state = skill_states.setdefault(skill_id, {"skill_id": skill_id})
        if mastery.get("mastered"):
            passed_levels = sum(
                bool(mastery.get(level))
                for level in ("base", "application", "transfer")
            )
            repaired = {
                "mastered": True,
                "mastery_level": 100,
                "evidence_count": max(passed_levels, int(state.get("evidence_count", 0) or 0)),
                "attempts": max(passed_levels, int(state.get("attempts", 0) or 0)),
                "successes": max(passed_levels, int(state.get("successes", 0) or 0)),
                "difficulty_max": "exam_level",
                "migrated_from_topic": legacy_topic,
            }
            if any(state.get(key) != value for key, value in repaired.items()):
                state.update(repaired)
                changed = True
    return changed


def select_next_focus_from_graph(dna: dict) -> str | None:
    migrate_trajectory_to_skill_graph(dna)
    return select_next_skill(dna.get("skills"))
