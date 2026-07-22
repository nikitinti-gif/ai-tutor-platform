def create_default_skill_state(skill_id: str) -> dict:
    return {
        "skill_id": skill_id,
        "mastery_level": 0,
        "evidence_count": 0,
        "difficulty_max": None,
        "error_types": [],
        "last_evidence_at": None,
        "skill_level": 50,
        "skill_confidence": 10,
        "attempts": 0,
        "successes": 0,
        "mistakes": 0,
        "trend": "stable",
    }
