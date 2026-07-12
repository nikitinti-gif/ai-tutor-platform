from src.skills.skill_state import create_default_skill_state


def detect_skill_from_check(check_result: dict) -> str:
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

    skill["attempts"] += 1

    if check_result.get("status") == "correct":
        skill["successes"] += 1
        skill["skill_level"] = min(100, skill["skill_level"] + 5)
        skill["skill_confidence"] = min(100, skill["skill_confidence"] + 10)
        skill["trend"] = "up"

    elif check_result.get("status") == "has_error":
        skill["mistakes"] += 1
        skill["skill_level"] = max(0, skill["skill_level"] - 4)
        skill["skill_confidence"] = min(100, skill["skill_confidence"] + 8)
        skill["trend"] = "down"

    else:
        skill["skill_confidence"] = max(0, skill["skill_confidence"] - 5)
        skill["trend"] = "uncertain"

    return dna