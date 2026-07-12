from datetime import datetime


def create_default_learning_dna(student_id: int) -> dict:
    return {
        "student_id": student_id,
        "identity": {
            "exam": None,
            "subject": None,
            "target_score": None,
        },
        "skills": {},
        "signals": [],
        "memory": {
            "last_topics": [],
            "last_errors": [],
            "last_successes": [],
        },
        "motivation": {
            "xp": 0,
            "streak_days": 0,
        },
        "trajectory": {
            "next_focus": None,
            "recommendations": [],
        },
        "predictions": {
            "estimated_score": None,
        },
        "ai_notes": [],
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }