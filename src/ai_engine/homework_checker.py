from src.ai_engine.llm_client import LLMClient
from src.ai_engine.parser import parse_homework_check_response


def check_homework_text(text: str) -> dict:
    client = LLMClient()

    raw_response = client.check_homework_text(text)
    result = parse_homework_check_response(raw_response)

    return result


def render_check_result_for_student(result: dict) -> str:
    if result["status"] == "correct":
        return (
            "✅ Решение принято!\n\n"
            f"{result['feedback']}\n\n"
            f"💡 {result['hint']}"
        )

    if result["status"] == "has_error":
        return (
            "🟡 Нашёл место, которое нужно перепроверить.\n\n"
            f"{result['feedback']}\n\n"
            f"❓ Подсказка: {result['hint']}"
        )

    return (
        "🔴 Нужна проверка преподавателя.\n\n"
        f"{result['feedback']}\n\n"
        f"💡 {result['hint']}"
    )