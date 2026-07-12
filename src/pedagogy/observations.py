def build_observation_from_check(check_result: dict) -> dict:
    return {
        "event": "homework_checked",
        "status": check_result.get("status"),
        "topic": check_result.get("topic") or "unknown",
        "error_type": check_result.get("error_type"),
        "confidence": check_result.get("confidence", 0.0),
        "facts": [
            f"AI status: {check_result.get('status')}",
            f"Topic: {check_result.get('topic') or 'unknown'}",
            f"Confidence: {check_result.get('confidence', 0.0)}",
        ],
    }