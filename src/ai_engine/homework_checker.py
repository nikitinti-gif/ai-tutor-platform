from src.ai_engine.parser import (
    parse_homework_check_response,
    parse_image_transcription_response,
)
from src.ai_engine.llm_client import LLMClient
from src.ai_engine.provider_clients import create_text_provider
from src.ai_engine.schemas import enforce_error_evidence


def check_homework_text(
    text: str,
    task_text: str | None = None,
    topic: str | None = None,
    synthetic_test: bool = False,
    provider_name: str = "gemini",
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

    client = create_text_provider(provider_name)

    raw_response = client.check_homework_text(
        text=text,
        task_text=task_text,
        topic=topic,
        synthetic_test=True,
    )
    result = parse_homework_check_response(raw_response)
    return enforce_error_evidence(result, text)


def check_homework_image(
    image_bytes: bytes,
    mime_type: str,
    task_text: str | None = None,
    topic: str | None = None,
    synthetic_test: bool = False,
    provider_name: str = "gemini",
    pilot_v2: bool = False,
) -> dict:
    pilot_allowed = pilot_v2 and provider_name == "qwen"
    if not synthetic_test and not pilot_allowed:
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

    if provider_name == "gemini":
        client = LLMClient()
    else:
        client = create_text_provider(provider_name)
        if not hasattr(client, "transcribe_homework_image"):
            raise ValueError(
                f"Провайдер {provider_name} не поддерживает изображения."
            )
    transcription_kwargs = {
        "image_bytes": image_bytes,
        "mime_type": mime_type,
        "synthetic_test": synthetic_test,
    }
    if pilot_allowed:
        transcription_kwargs["pilot_v2"] = True
    raw_transcription = client.transcribe_homework_image(
        **transcription_kwargs
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

    check_kwargs = {
        "text": transcription["transcription"],
        "task_text": task_text,
        "topic": topic,
        "synthetic_test": synthetic_test,
    }
    if pilot_allowed:
        check_kwargs["pilot_v2"] = True
    raw_response = client.check_homework_text(**check_kwargs)
    result = parse_homework_check_response(raw_response)
    result = enforce_error_evidence(result, transcription["transcription"])
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
