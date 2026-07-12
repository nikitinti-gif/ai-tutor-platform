def create_default_skill_state(skill_id: str) -> dict:
    return {
        "skill_id": skill_id,
        "skill_level": 50,
        "skill_confidence": 10,
        "attempts": 0,
        "successes": 0,
        "mistakes": 0,
        "trend": "stable",
    }