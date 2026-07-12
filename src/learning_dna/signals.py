def build_learning_signal_from_check(check_result: dict) -> dict:
    status = check_result.get("status")
    error_type = check_result.get("error_type")
    topic = check_result.get("topic")
    confidence = check_result.get("confidence", 0.0)

    if status == "correct":
        return {
            "type": "success",
            "topic": topic or "unknown",
            "signal": "Ученик успешно справился с заданием.",
            "confidence": confidence,
            "recommended_action": "Можно постепенно повышать сложность.",
        }

    if status == "has_error":
        return {
            "type": "mistake",
            "topic": topic or "unknown",
            "error_type": error_type or "unknown_error",
            "signal": "Обнаружена учебная ошибка, которую нужно закрепить.",
            "confidence": confidence,
            "recommended_action": "Добавить 2–3 задания на эту тему и дать короткую подсказку.",
        }

    return {
        "type": "unclear",
        "topic": topic or "unknown",
        "signal": "Решение не удалось уверенно проверить.",
        "confidence": confidence,
        "recommended_action": "Передать работу преподавателю на ручную проверку.",
    }