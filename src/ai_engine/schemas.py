HOMEWORK_CHECK_STATUSES = {
    "correct",
    "has_error",
    "unclear",
}


HOMEWORK_CHECK_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {
            "type": "string",
            "enum": sorted(HOMEWORK_CHECK_STATUSES),
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "feedback": {"type": "string"},
        "hint": {"type": "string"},
        "error_type": {"type": ["string", "null"]},
        "topic": {"type": ["string", "null"]},
    },
    "required": [
        "status",
        "confidence",
        "feedback",
        "hint",
        "error_type",
        "topic",
    ],
    "additionalProperties": False,
}


def default_homework_check_result() -> dict:
    return {
        "status": "unclear",
        "confidence": 0.0,
        "feedback": "Не удалось уверенно проверить решение.",
        "hint": (
            "Отправь условие задачи и решение ещё раз "
            "или дождись проверки преподавателя."
        ),
        "error_type": None,
        "topic": None,
        "needs_teacher_review": True,
    }


def _clean_optional_string(value) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        return None

    value = value.strip()

    return value or None


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

    feedback = _clean_optional_string(data.get("feedback"))
    hint = _clean_optional_string(data.get("hint"))

    if feedback:
        result["feedback"] = feedback

    if hint:
        result["hint"] = hint

    result["error_type"] = _clean_optional_string(
        data.get("error_type")
    )
    result["topic"] = _clean_optional_string(
        data.get("topic")
    )

    result["needs_teacher_review"] = (
        result["status"] == "unclear"
        or result["confidence"] < 0.85
    )

    return result
