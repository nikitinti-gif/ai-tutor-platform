HOMEWORK_CHECK_STATUSES = {
    "correct",
    "has_error",
    "unclear",
}

IMAGE_LEGIBILITY_STATUSES = {
    "readable",
    "partial",
    "unreadable",
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


IMAGE_TRANSCRIPTION_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "legibility": {
            "type": "string",
            "enum": sorted(IMAGE_LEGIBILITY_STATUSES),
        },
        "confidence": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "transcription": {"type": "string"},
    },
    "required": [
        "legibility",
        "confidence",
        "transcription",
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


def default_image_transcription_result() -> dict:
    return {
        "legibility": "unreadable",
        "confidence": 0.0,
        "transcription": "",
    }


def _clean_optional_string(value) -> str | None:
    if value is None or not isinstance(value, str):
        return None

    value = value.strip()
    return value or None


def _bounded_confidence(value) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return 0.0


def validate_homework_check_result(data: dict) -> dict:
    result = default_homework_check_result()

    if not isinstance(data, dict):
        return result

    required_fields = HOMEWORK_CHECK_RESPONSE_SCHEMA["required"]
    if any(field not in data for field in required_fields):
        return result

    status = data.get("status")
    feedback = _clean_optional_string(data.get("feedback"))
    hint = _clean_optional_string(data.get("hint"))

    if (
        status not in HOMEWORK_CHECK_STATUSES
        or not feedback
        or not hint
    ):
        return result

    raw_confidence = data.get("confidence")
    if isinstance(raw_confidence, bool):
        return result

    try:
        confidence = float(raw_confidence)
    except (TypeError, ValueError):
        return result

    if not 0.0 <= confidence <= 1.0:
        return result

    raw_error_type = data.get("error_type")
    raw_topic = data.get("topic")
    if raw_error_type is not None and not isinstance(raw_error_type, str):
        return result
    if raw_topic is not None and not isinstance(raw_topic, str):
        return result

    error_type = _clean_optional_string(raw_error_type)
    topic = _clean_optional_string(raw_topic)
    if raw_error_type is not None and error_type is None:
        return result
    if raw_topic is not None and topic is None:
        return result

    if status == "correct" and error_type is not None:
        return result
    if status == "has_error" and error_type is None:
        return result

    result.update(
        {
            "status": status,
            "confidence": confidence,
            "feedback": feedback,
            "hint": hint,
            "error_type": error_type,
            "topic": topic,
            "needs_teacher_review": (
                status == "unclear" or confidence < 0.85
            ),
        }
    )
    return result


def validate_image_transcription_result(data: dict) -> dict:
    result = default_image_transcription_result()

    if not isinstance(data, dict):
        return result

    legibility = data.get("legibility")
    if legibility in IMAGE_LEGIBILITY_STATUSES:
        result["legibility"] = legibility

    result["confidence"] = _bounded_confidence(
        data.get("confidence", 0.0)
    )
    transcription = _clean_optional_string(data.get("transcription"))
    result["transcription"] = transcription or ""

    if result["legibility"] == "readable" and not transcription:
        result["legibility"] = "partial"

    return result
