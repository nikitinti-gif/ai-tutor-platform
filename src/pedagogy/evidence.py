def build_evidence(observation: dict, learning_dna: dict | None) -> list[dict]:
    evidence = []

    status = observation.get("status")
    topic = observation.get("topic")
    confidence = observation.get("confidence", 0.0)

    if status == "has_error":
        evidence.append({
            "rule": "AI_FOUND_ERROR",
            "weight": 0.6,
            "description": "AI обнаружил ошибку в решении ученика.",
        })

    if status == "correct":
        evidence.append({
            "rule": "AI_CONFIRMED_SUCCESS",
            "weight": 0.5,
            "description": "AI подтвердил успешное решение.",
        })

    if status == "unclear" or confidence < 0.85:
        evidence.append({
            "rule": "LOW_CONFIDENCE",
            "weight": 0.9,
            "description": "Проверка недостаточно уверенная, нужна ручная проверка.",
        })

    if learning_dna:
        signals = learning_dna.get("signals", [])
        repeated_topic_count = sum(
            1 for signal in signals
            if signal.get("topic") == topic and signal.get("type") == "mistake"
        )

        if repeated_topic_count >= 3:
            evidence.append({
                "rule": "REPEATED_TOPIC_MISTAKE",
                "weight": 0.95,
                "description": f"По теме «{topic}» уже {repeated_topic_count} ошибок.",
            })

    return evidence