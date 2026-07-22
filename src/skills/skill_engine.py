from datetime import datetime

from src.skills.skill_graph import get_skill, migrate_legacy_focus
from src.skills.skill_state import create_default_skill_state


def detect_skill_from_check(check_result: dict) -> str:
    explicit_skill = check_result.get("skill_id")
    if explicit_skill and get_skill(explicit_skill):
        return explicit_skill

    migrated_topic = migrate_legacy_focus(check_result.get("topic"))
    if migrated_topic:
        return migrated_topic

    error_type = check_result.get("error_type")
    topic = check_result.get("topic")

    if error_type == "logic_condition_error":
        return "conditional_logic"

    if error_type == "unclear_solution":
        return "algorithm_explanation"

    if topic == "Информатика":
        return "informatics_basics"

    return "general_learning"


def update_skill_after_check(dna: dict, check_result: dict) -> dict:
    skill_id = detect_skill_from_check(check_result)

    dna.setdefault("skills", {})

    if skill_id not in dna["skills"]:
        dna["skills"][skill_id] = create_default_skill_state(skill_id)

    skill = dna["skills"][skill_id]

    level_results = check_result.get("level_results")
    evidence = level_results if isinstance(level_results, list) and level_results else [check_result]
    skill["attempts"] += len(evidence)
    skill["evidence_count"] = skill.get("evidence_count", 0) + len(evidence)
    skill["last_evidence_at"] = datetime.now().isoformat(timespec="seconds")

    difficulty = check_result.get("difficulty") or check_result.get("diagnostic_level")
    difficulty_rank = {None: 0, "base": 1, "application": 2, "transfer": 3,
                       "exam": 3, "exam_level": 3, 1: 1, 2: 2, 3: 3}
    previous = skill.get("difficulty_max")
    if difficulty_rank.get(difficulty, 0) > difficulty_rank.get(previous, 0):
        skill["difficulty_max"] = difficulty

    correct_count = sum(item.get("status") == "correct" for item in evidence)
    mistake_count = sum(item.get("status") == "has_error" for item in evidence)
    unclear_count = len(evidence) - correct_count - mistake_count
    skill["successes"] += correct_count
    skill["mistakes"] += mistake_count

    if correct_count == len(evidence):
        skill["skill_level"] = min(100, skill["skill_level"] + 5 * correct_count)
        skill["skill_confidence"] = min(100, skill["skill_confidence"] + 10 * correct_count)
        skill["trend"] = "up"
        skill["mastery_level"] = min(100, skill.get("mastery_level", 0) + 20 * correct_count)

    elif check_result.get("status") == "has_error":
        skill["skill_level"] = max(0, skill["skill_level"] - 4 * max(1, mistake_count))
        skill["skill_confidence"] = min(100, skill["skill_confidence"] + 8)
        skill["trend"] = "down"
        skill["mastery_level"] = max(0, skill.get("mastery_level", 0) - 10)
        error_type = check_result.get("error_type")
        if error_type and error_type not in skill["error_types"]:
            skill["error_types"].append(error_type)

    elif unclear_count:
        skill["skill_confidence"] = max(0, skill["skill_confidence"] - 5)
        skill["trend"] = "uncertain"

    return dna
