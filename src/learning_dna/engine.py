from datetime import datetime

from src.ai_engine.diagnostics import confirmed_case_to_check_result
from src.learning_dna.profile import create_default_learning_dna
from src.learning_dna.signals import build_learning_signal_from_check
from src.learning_dna.trajectory import (
    TOPIC_SEQUENCE,
    migrate_trajectory_to_skill_graph,
    select_next_focus_from_graph,
    select_next_topic,
)
from src.skills.skill_graph import get_skill, get_skill_name, migrate_legacy_focus
from src.skills.skill_engine import update_skill_after_check


def restore_next_focus_from_mastery(dna: dict) -> bool:
    """Restore a missing next focus for profiles saved by an older release.

    Returns True only when the profile was changed and must be persisted.
    Existing teacher-selected or error-driven focuses are never overwritten.
    """
    trajectory = dna.setdefault("trajectory", {})
    changed = migrate_trajectory_to_skill_graph(dna)
    if trajectory.get("next_focus_skill_id"):
        return changed

    topic_mastery = dna.get("topic_mastery") or {}
    mastered_topics = {
        topic
        for topic, mastery in topic_mastery.items()
        if isinstance(mastery, dict) and mastery.get("mastered")
    }
    if not mastered_topics:
        return changed

    next_topic = None
    for topic in reversed(TOPIC_SEQUENCE):
        if topic in mastered_topics:
            next_topic = select_next_topic(topic, topic_mastery)
            break

    if not next_topic:
        return changed

    trajectory["next_focus"] = next_topic
    dna["updated_at"] = datetime.now().isoformat(timespec="seconds")
    migrate_trajectory_to_skill_graph(dna)
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
    completed_skill = migrate_legacy_focus(topic)
    if isinstance(mastery, dict) and mastery.get("topic_mastered") and completed_skill:
        state = dna.setdefault("skills", {}).setdefault(completed_skill, {})
        passed_levels = sum(
            bool(mastery.get(level))
            for level in ("base", "application", "transfer")
        )
        state.update({
            "skill_id": completed_skill,
            "mastered": True,
            "mastery_level": 100,
            "evidence_count": max(passed_levels, int(state.get("evidence_count", 0) or 0)),
            "attempts": max(passed_levels, int(state.get("attempts", 0) or 0)),
            "successes": max(passed_levels, int(state.get("successes", 0) or 0)),
            "difficulty_max": "exam_level",
        })
        next_skill = select_next_focus_from_graph(dna)
        dna["trajectory"]["next_focus_skill_id"] = next_skill
        dna["trajectory"]["next_focus"] = get_skill_name(next_skill) if next_skill else None
    dna["updated_at"] = datetime.now().isoformat(timespec="seconds")

    return dna


def _confirmed_probe_id(case: dict) -> str | None:
    """Return the failed locally checked probe that proves this diagnosis."""
    for evidence in reversed(case.get("evidence", [])):
        if (
            evidence.get("kind") == "control_probe"
            and evidence.get("is_correct") is False
        ):
            return evidence.get("probe_id")
    return None


def apply_confirmed_ege_diagnostics(
    current_dna: dict | None,
    student_id: int,
    attempt,
) -> tuple[dict, dict]:
    """Persist confirmed KЕГЭ evidence exactly once and rebuild the study plan.

    Idempotency is based on the immutable exam attempt id, task number and
    control-probe id. Unconfirmed cases never enter Learning DNA.
    """
    dna = current_dna or create_default_learning_dna(student_id)
    processed = dna.setdefault("processed_evidence_ids", [])
    processed_set = set(processed)
    applied_ids = []

    confirmed = [
        case
        for _, case in sorted(attempt.diagnostics.items())
        if case.get("status") == "confirmed"
    ]
    for case in confirmed:
        probe_id = _confirmed_probe_id(case)
        if not probe_id:
            continue
        evidence_id = (
            f"ege:{attempt.attempt_id}:task:{case['task_number']}:probe:{probe_id}"
        )
        if evidence_id in processed_set:
            continue

        check_result = confirmed_case_to_check_result(case)
        check_result.update({
            "evidence_id": evidence_id,
            "attempt_id": attempt.attempt_id,
            "difficulty": "exam_level",
        })
        dna = update_learning_dna_after_check(dna, student_id, check_result)
        processed.append(evidence_id)
        processed_set.add(evidence_id)
        applied_ids.append(evidence_id)

    plan = []
    seen_steps = set()
    for case in confirmed:
        probe_id = _confirmed_probe_id(case)
        if not probe_id:
            continue
        step_key = (case.get("task_number"), case.get("failed_step"))
        if step_key in seen_steps:
            continue
        seen_steps.add(step_key)
        skill_ids = case.get("skill_ids") or []
        skill_id = skill_ids[0] if skill_ids else None
        skill = get_skill(skill_id) if skill_id else None
        plan.append({
            "order": len(plan) + 1,
            "task_number": case.get("task_number"),
            "skill_id": skill_id,
            "skill_name": get_skill_name(skill_id) if skill_id else case.get("task_title"),
            "failed_step": case.get("failed_step"),
            "action": case.get("learning_action"),
            "prerequisites": list((skill or {}).get("prerequisites", [])),
            "evidence_status": "confirmed",
            "confidence": case.get("confidence"),
        })

    trajectory = dna.setdefault("trajectory", {})
    trajectory["individual_plan"] = plan
    if plan:
        first = plan[0]
        trajectory["next_focus_skill_id"] = first["skill_id"]
        trajectory["next_focus"] = first["failed_step"]
        trajectory["recommendations"] = [
            item["action"] for item in plan if item.get("action")
        ]
    else:
        trajectory["next_focus_skill_id"] = None
        trajectory["next_focus"] = None
        trajectory["recommendations"] = []

    dna["updated_at"] = datetime.now().isoformat(timespec="seconds")
    return dna, {
        "applied_count": len(applied_ids),
        "applied_evidence_ids": applied_ids,
        "confirmed_count": len(confirmed),
        "plan_size": len(plan),
        "next_focus": trajectory.get("next_focus"),
    }
