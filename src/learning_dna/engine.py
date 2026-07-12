from datetime import datetime

from src.learning_dna.profile import create_default_learning_dna
from src.learning_dna.signals import build_learning_signal_from_check
from src.skills.skill_engine import update_skill_after_check


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

    if signal["type"] == "unclear":
        dna["trajectory"]["recommendations"].append("Нужна ручная проверка преподавателя.")
    
    dna = update_skill_after_check(dna, check_result)
    dna["updated_at"] = datetime.now().isoformat(timespec="seconds")

    return dna