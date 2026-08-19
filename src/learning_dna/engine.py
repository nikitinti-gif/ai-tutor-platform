from datetime import datetime
from functools import cmp_to_key

from src.ai_engine.diagnostic_evidence_gate import valid_diagnostic_evidence
from src.ai_engine.diagnostics import confirmed_case_to_check_result
from src.learning_dna.profile import create_default_learning_dna
from src.learning_dna.signals import build_learning_signal_from_check
from src.learning_dna.trajectory import (
    TOPIC_SEQUENCE,
    migrate_trajectory_to_skill_graph,
    select_next_focus_from_graph,
    select_next_topic,
)
from src.skills.skill_graph import (
    get_skill, get_skill_name, migrate_legacy_focus, prerequisite_path,
)
from src.skills.skill_engine import update_skill_after_check


def restore_next_focus_from_mastery(dna: dict) -> bool:
    trajectory = dna.setdefault("trajectory", {})
    changed = migrate_trajectory_to_skill_graph(dna)
    if trajectory.get("next_focus_skill_id"):
        return changed
    topic_mastery = dna.get("topic_mastery") or {}
    mastered_topics = {topic for topic, mastery in topic_mastery.items() if isinstance(mastery, dict) and mastery.get("mastered")}
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
            "base": bool(mastery.get("base")), "application": bool(mastery.get("application")),
            "transfer": bool(mastery.get("transfer")), "mastered": bool(mastery.get("topic_mastered")),
            "knowledge_boundary": check_result.get("knowledge_boundary"),
        }
        if mastery.get("topic_mastered"):
            next_topic = select_next_topic(topic, dna["topic_mastery"])
            dna["trajectory"]["next_focus"] = next_topic
            dna["trajectory"]["recommendations"].append(f"Тема «{topic}» подтверждённо освоена на трёх уровнях. " + (f"Следующая тема: «{next_topic}»." if next_topic else "Следующую тему выбирает преподаватель."))
        else:
            dna["trajectory"]["next_focus"] = topic
    if signal["type"] == "unclear":
        dna["trajectory"]["recommendations"].append("Нужна ручная проверка преподавателя.")
    dna = update_skill_after_check(dna, check_result)
    completed_skill = migrate_legacy_focus(topic)
    if isinstance(mastery, dict) and mastery.get("topic_mastered") and completed_skill:
        state = dna.setdefault("skills", {}).setdefault(completed_skill, {})
        passed_levels = sum(bool(mastery.get(level)) for level in ("base", "application", "transfer"))
        state.update({"skill_id": completed_skill, "mastered": True, "mastery_level": 100,
                      "evidence_count": max(passed_levels, int(state.get("evidence_count", 0) or 0)),
                      "attempts": max(passed_levels, int(state.get("attempts", 0) or 0)),
                      "successes": max(passed_levels, int(state.get("successes", 0) or 0)), "difficulty_max": "exam_level"})
        next_skill = select_next_focus_from_graph(dna)
        dna["trajectory"]["next_focus_skill_id"] = next_skill
        dna["trajectory"]["next_focus"] = get_skill_name(next_skill) if next_skill else None
    dna["updated_at"] = datetime.now().isoformat(timespec="seconds")
    return dna


def _confirmed_evidence(case: dict) -> dict | None:
    """Return only a failed, complete and auditable probe allowed into Learning DNA."""
    for evidence in reversed(valid_diagnostic_evidence(case)):
        if evidence.get("validator_result") is False and evidence.get("is_correct") is False:
            return evidence
    return None


def _confirmed_probe_id(case: dict) -> str | None:
    evidence = _confirmed_evidence(case)
    return evidence.get("probe_id") if evidence else None


def apply_confirmed_ege_diagnostics(current_dna: dict | None, student_id: int, attempt) -> tuple[dict, dict]:
    """Persist confirmed KЕГЭ evidence exactly once and rebuild the study plan.

    Confirmed status alone is insufficient: the case must contain a complete
    fail-closed evidence chain produced by the strict diagnostic gate.
    """
    dna = current_dna or create_default_learning_dna(student_id)
    processed = dna.setdefault("processed_evidence_ids", [])
    processed_set = set(processed)
    applied_ids = []
    confirmed = [case for _, case in sorted(attempt.diagnostics.items()) if case.get("status") == "confirmed" and _confirmed_evidence(case)]
    for case in confirmed:
        probe_id = _confirmed_probe_id(case)
        evidence_id = f"ege:{attempt.attempt_id}:task:{case['task_number']}:probe:{probe_id}"
        if evidence_id in processed_set:
            continue
        evidence = _confirmed_evidence(case)
        check_result = confirmed_case_to_check_result(case)
        evidence_skill_id = evidence.get("skill_id") if evidence else None
        if evidence_skill_id and get_skill(evidence_skill_id):
            check_result["skill_id"] = evidence_skill_id
        check_result.update({
            "evidence_id": evidence_id,
            "attempt_id": attempt.attempt_id,
            "difficulty": "exam_level",
            "hypothesis_id": evidence.get("hypothesis_id") if evidence else None,
            "probe_id": evidence.get("probe_id") if evidence else None,
        })
        dna = update_learning_dna_after_check(dna, student_id, check_result)
        processed.append(evidence_id)
        processed_set.add(evidence_id)
        applied_ids.append(evidence_id)
    plan = []
    seen_skills = set()
    for case in confirmed:
        evidence = _confirmed_evidence(case)
        skill_ids = case.get("skill_ids") or []
        evidence_skill_id = evidence.get("skill_id") if evidence else None
        skill_id = evidence_skill_id if evidence_skill_id and get_skill(evidence_skill_id) else (skill_ids[0] if skill_ids else None)
        if not skill_id or skill_id in seen_skills:
            continue
        seen_skills.add(skill_id)
        skill = get_skill(skill_id) if skill_id else None
        plan.append({"order": len(plan) + 1, "task_number": case.get("task_number"), "skill_id": skill_id,
                     "skill_name": get_skill_name(skill_id) if skill_id else case.get("task_title"),
                     "failed_step": case.get("failed_step"), "action": case.get("learning_action"),
                     "prerequisites": list((skill or {}).get("prerequisites", [])), "evidence_status": "confirmed",
                     "confidence": case.get("confidence"),
                     "exam_tasks": list((skill or {}).get("exam_tasks", [])),
                     "learning_path": ["foundation", "basic", "intermediate", "transfer", "exam", "exam_transfer"],
                     "learning_support_status": "ready" if case.get("task_number") in {5, 14, 27} else "learning_module_pending"})
    # Dependency order wins over exam number whenever two confirmed gaps depend
    # on each other. The same global skill can occur only once in the course.
    def dependency_order(left: dict, right: dict) -> int:
        if left["skill_id"] in prerequisite_path(right["skill_id"]):
            return -1
        if right["skill_id"] in prerequisite_path(left["skill_id"]):
            return 1
        return 0  # stable sort retains evidence/exam order for unrelated gaps

    plan.sort(key=cmp_to_key(dependency_order))
    for order, item in enumerate(plan, 1):
        item["order"] = order
    trajectory = dna.setdefault("trajectory", {})
    trajectory["individual_plan"] = plan
    if plan:
        first = plan[0]
        trajectory["next_focus_skill_id"] = first["skill_id"]
        trajectory["next_focus"] = first["failed_step"]
        trajectory["recommendations"] = [item["action"] for item in plan if item.get("action")]
    else:
        trajectory["next_focus_skill_id"] = None
        trajectory["next_focus"] = None
        trajectory["recommendations"] = []
    dna["updated_at"] = datetime.now().isoformat(timespec="seconds")
    return dna, {"applied_count": len(applied_ids), "applied_evidence_ids": applied_ids,
                 "confirmed_count": len(confirmed), "plan_size": len(plan), "next_focus": trajectory.get("next_focus")}


def set_ege_remediation_status(dna: dict, task_number: int, status: str) -> dict:
    if status not in {"remediating", "retesting", "mastered"}:
        raise ValueError("Неизвестный статус обучающего цикла.")
    trajectory = dna.setdefault("trajectory", {})
    for item in trajectory.get("individual_plan", []):
        if item.get("task_number") == task_number:
            item["learning_status"] = status
            break
    trajectory["remediation_status"] = status
    dna["updated_at"] = datetime.now().isoformat(timespec="seconds")
    return dna


def confirm_ege_remediation_mastery(dna: dict, task_number: int, attempt_id: str, remediation: dict | None = None) -> dict:
    evidence_id = f"ege:{attempt_id}:task:{task_number}:remediation:verified"
    history = list((remediation or {}).get("stage_history", []))
    round_id = (remediation or {}).get("learning_round")
    successful = [
        item for item in history
        if item.get("learning_round") == round_id
        and item.get("validator_result") is True
        and item.get("question")
        and item.get("canonical_answer") is not None
        and item.get("student_answer") is not None
        and item.get("timestamp") is not None
    ]
    stages = [item.get("stage") for item in successful[-3:]]
    combined = remediation or {}
    learning_history = list((combined.get("learning_path") or {}).get("history", []))
    bank = combined.get("task_bank") or {}
    bank_history = list(bank.get("history", []))
    learning_difficulties = {
        item.get("difficulty") for item in learning_history
        if item.get("validator_result") is True
    }
    bank_successes = {
        item.get("task_id") for item in bank_history
        if item.get("validator_result") is True
    }
    progressive_path_verified = (
        {"foundation", "basic", "intermediate", "transfer", "exam", "exam_transfer"}
        <= learning_difficulties
        and set(bank.get("sequence") or []) <= bank_successes
        and len(bank_successes) >= 2
    )
    if stages != ["control", "retest", "verification"] and not progressive_path_verified:
        raise ValueError("Нельзя подтвердить навык без полного независимого evidence chain.")
    processed = dna.setdefault("processed_evidence_ids", [])
    dna = set_ege_remediation_status(dna, task_number, "mastered")
    if evidence_id in processed:
        return dna
    plan_item = next((item for item in dna.get("trajectory", {}).get("individual_plan", []) if item.get("task_number") == task_number), {})
    skill_id = plan_item.get("skill_id")
    if skill_id:
        state = dna.setdefault("skills", {}).setdefault(skill_id, {"skill_id": skill_id})
        state.update({"mastered": True, "mastery_level": 100,
                      "evidence_count": int(state.get("evidence_count", 0) or 0) + 3,
                      "attempts": int(state.get("attempts", 0) or 0) + 3,
                      "successes": int(state.get("successes", 0) or 0) + 3,
                      "difficulty_max": "exam_level", "last_evidence_id": evidence_id,
                      "remediation_evidence": successful[-3:] if successful else (
                          learning_history + bank_history
                      )})
        next_skill = select_next_focus_from_graph(dna)
        trajectory = dna["trajectory"]
        trajectory["next_focus_skill_id"] = next_skill
        trajectory["next_focus"] = get_skill_name(next_skill) if next_skill else None
    processed.append(evidence_id)
    dna["updated_at"] = datetime.now().isoformat(timespec="seconds")
    return dna
