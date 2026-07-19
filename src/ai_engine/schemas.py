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
        "error_evidence": {"type": ["string", "null"]},
        "error_explanation": {"type": ["string", "null"]},
    },
    "required": [
        "status",
        "confidence",
        "feedback",
        "hint",
        "error_type",
        "topic",
        "error_evidence",
        "error_explanation",
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
        "error_evidence": None,
        "error_explanation": None,
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

    status = data.get("status")
    if status in HOMEWORK_CHECK_STATUSES:
        result["status"] = status

    result["confidence"] = _bounded_confidence(
        data.get("confidence", 0.0)
    )

    feedback = _clean_optional_string(data.get("feedback"))
    hint = _clean_optional_string(data.get("hint"))
    if feedback:
        result["feedback"] = feedback
    if hint:
        result["hint"] = hint

    result["error_type"] = _clean_optional_string(
        data.get("error_type")
    )
    result["topic"] = _clean_optional_string(data.get("topic"))
    result["error_evidence"] = _clean_optional_string(
        data.get("error_evidence")
    )
    result["error_explanation"] = _clean_optional_string(
        data.get("error_explanation")
    )
    result["needs_teacher_review"] = (
        result["status"] == "unclear"
        or result["confidence"] < 0.85
    )

    return result


def _normalize_evidence_text(value: str) -> str:
    return " ".join(value.casefold().split())


def enforce_error_evidence(result: dict, student_solution: str) -> dict:
    if result.get("status") != "has_error":
        return result

    evidence = result.get("error_evidence")
    explanation = result.get("error_explanation")
    normalized_solution = _normalize_evidence_text(student_solution or "")
    normalized_evidence = _normalize_evidence_text(evidence or "")
    evidence_is_present = bool(
        normalized_evidence
        and normalized_evidence in normalized_solution
    )

    if not evidence_is_present or not explanation:
        result["provider_feedback"] = result.get("feedback")
        result["status"] = "unclear"
        result["confidence"] = 0.0
        result["feedback"] = (
            "AI предположил ошибку, но не подтвердил её конкретным "
            "фрагментом решения."
        )
        result["hint"] = "Требуется проверка преподавателя."
        result["error_type"] = "unclear_solution"
        result["needs_teacher_review"] = True
        return result

    result["provider_feedback"] = result.get("feedback")
    safe_evidence = evidence[:240]
    safe_explanation = explanation[:700]
    result["feedback"] = (
        f"Ошибка в фрагменте «{safe_evidence}». {safe_explanation}"
    )
    result["needs_teacher_review"] = result["confidence"] < 0.85
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
