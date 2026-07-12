def build_reasoning(observation: dict, evidence: list[dict]) -> str:
    rules = [item["rule"] for item in evidence]
    topic = observation.get("topic", "unknown")

    if "LOW_CONFIDENCE" in rules:
        return (
            "Система не должна автоматически отвечать ученику, потому что уверенность проверки низкая. "
            "Лучшее педагогическое решение — передать работу преподавателю."
        )

    if "REPEATED_TOPIC_MISTAKE" in rules:
        return (
            f"По теме «{topic}» наблюдаются повторяющиеся ошибки. "
            "Это означает, что навык пока не закреплён и требует целевого повторения."
        )

    if "AI_FOUND_ERROR" in rules:
        return (
            f"В решении по теме «{topic}» обнаружена ошибка. "
            "Нужно не давать готовый ответ, а направить ученика к самостоятельному исправлению."
        )

    if "AI_CONFIRMED_SUCCESS" in rules:
        return (
            f"Решение по теме «{topic}» выглядит успешным. "
            "Можно закрепить результат и постепенно повышать сложность."
        )

    return "Недостаточно данных для уверенного педагогического решения."