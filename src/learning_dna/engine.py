from datetime import datetime

from src.learning_dna.profile import create_default_learning_dna
from src.learning_dna.signals import build_learning_signal_from_check
from src.learning_dna.trajectory import TOPIC_SEQUENCE, select_next_topic
from src.skills.skill_engine import update_skill_after_check


def restore_next_focus_from_mastery(dna: dict) -> bool:
    """Restore a missing next focus for profiles saved by an older release.

    Returns True only when the profile was changed and must be persisted.
    Existing teacher-selected or error-driven focuses are never overwritten.
    """
    trajectory = dna.setdefault("trajectory", {})
    if trajectory.get("next_focus"):
        return False

    topic_mastery = dna.get("topic_mastery") or {}
    mastered_topics = {
        topic
        for topic, mastery in topic_mastery.items()
        if isinstance(mastery, dict) and mastery.get("mastered")
    }
    if not mastered_topics:
        return False

    next_topic = None
    for topic in reversed(TOPIC_SEQUENCE):
        if topic in mastered_topics:
            next_topic = select_next_topic(topic, topic_mastery)
            break

    if not next_topic:
        return False

    trajectory["next_focus"] = next_topic
    dna["updated_at"] = datetime.now().isoformat(timespec="seconds")
    return True


def update_learning_dna_after_check(current_dna: dict | None, student_id: int, check_result: dict) -> dict:
    dna = current_dna or create_default_learning_dna(student_id)

    signal = build_learning_signal_from_check(check_result)
    dna["signals"].append(signal)

    topic = signal.get("topic", "unknown")

    if topic not in dna["memory"]["last_topics"]:
        dna["memory"]["last_topics"].append(topic)

    if signal["type"] == "mistake":
        dna["memory"]["last_errors"].append(signal)
        dna["trajectory"]["next_focus"] = topic
        dna["trajectory"]["recommendations"].append(signal["recommended_action"])

    if signal["type"] == "success":
        dna["memory"]["last_successes"].append(signal)
        dna["motivation"]["xp"] += 25

    mastery = check_result.get("diagnostic_mastery")
    if isinstance(mastery, dict) and topic != "unknown":
        dna.setdefault("topic_mastery", {})[topic] = {
            "base": bool(mastery.get("base")),
            "application": bool(mastery.get("application")),
            "transfer": bool(mastery.get("transfer")),
            "mastered": bool(mastery.get("topic_mastered")),
            "knowledge_boundary": check_result.get("knowledge_boundary"),
        }
        if mastery.get("topic_mastered"):
            next_topic = select_next_topic(topic, dna["topic_mastery"])
            dna["trajectory"]["next_focus"] = next_topic
            dna["trajectory"]["recommendations"].append(
                f"Тема «{topic}» подтверждённо освоена на трёх уровнях. "
                + (
                    f"Следующая тема: «{next_topic}»."
                    if next_topic
                    else "Следующую тему выбирает преподаватель."
                )
            )
        else:
            dna["trajectory"]["next_focus"] = topic

    if signal["type"] == "unclear":
        dna["trajectory"]["recommendations"].append("Нужна ручная проверка преподавателя.")
    
    dna = update_skill_after_check(dna, check_result)
    dna["updated_at"] = datetime.now().isoformat(timespec="seconds")

    return dna
