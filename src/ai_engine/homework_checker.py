from src.ai_engine.llm_client import LLMClient
from src.ai_engine.parser import (
    parse_homework_check_response,
    parse_image_transcription_response,
)


def check_homework_text(
    text: str,
    task_text: str | None = None,
    topic: str | None = None,
    synthetic_test: bool = False,
) -> dict:
    if not synthetic_test:
        return {
            "status": "unclear",
            "confidence": 0.0,
            "feedback": (
                "Реальная AI-проверка пока тестируется только "
                "на искусственных примерах."
            ),
            "hint": "Дождись проверки преподавателя.",
            "error_type": None,
            "topic": topic,
            "needs_teacher_review": True,
        }

    client = LLMClient()

    raw_response = client.check_homework_text(
        text=text,
        task_text=task_text,
        topic=topic,
        synthetic_test=True,
    )
    result = parse_homework_check_response(raw_response)

    return result


def check_homework_image(
    image_bytes: bytes,
    mime_type: str,
    task_text: str | None = None,
    topic: str | None = None,
    synthetic_test: bool = False,
) -> dict:
    if not synthetic_test:
        return {
            "status": "unclear",
            "confidence": 0.0,
            "feedback": (
                "Проверка реальных фотографий пока не подключена."
            ),
            "hint": "Дождись проверки преподавателя.",
            "error_type": None,
            "topic": topic,
            "needs_teacher_review": True,
        }

    client = LLMClient()
    raw_transcription = client.transcribe_homework_image(
        image_bytes=image_bytes,
        mime_type=mime_type,
        synthetic_test=True,
    )
    transcription = parse_image_transcription_response(raw_transcription)

    if transcription["legibility"] != "readable":
        return {
            "status": "unclear",
            "confidence": transcription["confidence"],
            "feedback": (
                "Изображение недостаточно читаемо для надёжной проверки."
            ),
            "hint": (
                "Сделай новое фото без размытия, чтобы всё решение "
                "и отступы были видны."
            ),
            "error_type": "unreadable_image",
            "topic": topic,
            "needs_teacher_review": True,
            "image_legibility": transcription["legibility"],
            "image_transcription": transcription["transcription"],
        }

    raw_response = client.check_homework_text(
        text=transcription["transcription"],
        task_text=task_text,
        topic=topic,
        synthetic_test=True,
    )
    result = parse_homework_check_response(raw_response)
    result["image_legibility"] = transcription["legibility"]
    result["image_transcription"] = transcription["transcription"]

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
