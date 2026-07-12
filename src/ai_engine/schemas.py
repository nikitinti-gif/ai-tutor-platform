HOMEWORK_CHECK_STATUSES = {
    "correct",
    "has_error",
    "unclear",
}


def default_homework_check_result() -> dict:
    return {
        "status": "unclear",
        "confidence": 0.0,
        "feedback": "Не удалось уверенно проверить решение.",
        "hint": "Пожалуйста, отправь более чёткое фото или дождись проверки преподавателя.",
        "error_type": None,
        "topic": None,
        "needs_teacher_review": True,
    }


def validate_homework_check_result(data: dict) -> dict:
    result = default_homework_check_result()

    if not isinstance(data, dict):
        return result

    status = data.get("status")

    if status in HOMEWORK_CHECK_STATUSES:
        result["status"] = status

    try:
        confidence = float(data.get("confidence", 0.0))
        result["confidence"] = max(0.0, min(confidence, 1.0))
    except (TypeError, ValueError):
        result["confidence"] = 0.0

    result["feedback"] = data.get("feedback") or result["feedback"]
    result["hint"] = data.get("hint") or result["hint"]
    result["error_type"] = data.get("error_type")
    result["topic"] = data.get("topic")

    result["needs_teacher_review"] = (
        result["status"] == "unclear"
        or result["confidence"] < 0.85
    )

    return result