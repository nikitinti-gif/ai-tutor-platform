def build_decision(observation: dict, evidence: list[dict]) -> dict:
    rules = [item["rule"] for item in evidence]
    topic = observation.get("topic", "unknown")

    if "LOW_CONFIDENCE" in rules:
        return {
            "priority": topic,
            "decision_type": "teacher_review",
            "teacher_attention": True,
            "difficulty": "unknown",
        }

    if "REPEATED_TOPIC_MISTAKE" in rules:
        return {
            "priority": topic,
            "decision_type": "repeat_skill",
            "teacher_attention": True,
            "difficulty": "basic",
        }

    if "AI_FOUND_ERROR" in rules:
        return {
            "priority": topic,
            "decision_type": "guided_correction",
            "teacher_attention": False,
            "difficulty": "basic",
        }

    if "AI_CONFIRMED_SUCCESS" in rules:
        return {
            "priority": topic,
            "decision_type": "increase_difficulty",
            "teacher_attention": False,
            "difficulty": "medium",
        }

    return {
        "priority": topic,
        "decision_type": "collect_more_data",
        "teacher_attention": True,
        "difficulty": "unknown",
    }