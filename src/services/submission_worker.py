import asyncio
import logging
from io import BytesIO

from aiogram import Bot

from config import (
    ADMIN_TELEGRAM_ID,
    SYNTHETIC_WORKER_INTERVAL_SECONDS,
    SYNTHETIC_WORKER_MAX_ATTEMPTS,
)
from src.ai_engine.homework_checker import check_homework_image
from src.repositories.submission_repository import SubmissionRepository


logger = logging.getLogger(__name__)


def _clip(value: object, limit: int) -> str:
    text = str(value or "—")
    return text if len(text) <= limit else f"{text[:limit - 1]}…"


def format_analysis_for_teacher(submission_id: str, result: dict) -> str:
    transcription = _clip(result.get("image_transcription"), 1200)
    error_type = _clip(result.get("error_type"), 120)
    feedback = _clip(result.get("feedback"), 1000)
    hint = _clip(result.get("hint"), 700)
    return (
        "🤖 Gemini обработал синтетическую работу\n\n"
        f"Номер: {submission_id}\n"
        f"Статус: {result['status']}\n"
        f"Уверенность: {float(result['confidence']):.2f}\n"
        f"Тип ошибки: {error_type}\n\n"
        f"Транскрипция:\n{transcription}\n\n"
        f"Анализ:\n{feedback}\n\n"
        f"Рекомендация:\n{hint}\n\n"
        "Результат отправлен только преподавателю."
    )


async def _download_submission_photo(bot: Bot, file_id: str) -> bytes:
    telegram_file = await bot.get_file(file_id)
    buffer = BytesIO()
    try:
        await bot.download_file(telegram_file.file_path, destination=buffer)
        return buffer.getvalue()
    finally:
        buffer.close()


async def process_next_synthetic_submission(bot: Bot) -> bool:
    submission = await asyncio.to_thread(
        SubmissionRepository.claim_next_synthetic,
        SYNTHETIC_WORKER_MAX_ATTEMPTS,
    )
    if not submission:
        return False

    submission_id = submission["submission_id"]
    try:
        image_bytes = await _download_submission_photo(
            bot,
            submission["telegram_file_id"],
        )
        if not image_bytes:
            raise ValueError("Telegram вернул пустое изображение.")

        result = await asyncio.to_thread(
            check_homework_image,
            image_bytes=image_bytes,
            mime_type="image/jpeg",
            task_text=None,
            topic="Синтетический пилот",
            synthetic_test=True,
            provider_name="gemini",
        )
        await asyncio.to_thread(
            SubmissionRepository.save_analysis,
            submission_id,
            result,
        )
        logger.info(
            "Synthetic submission processed: id=%s status=%s confidence=%.2f",
            submission_id,
            result["status"],
            result["confidence"],
        )
    except Exception as error:
        logger.exception(
            "Synthetic submission processing failed: %s",
            submission_id,
        )
        await asyncio.to_thread(
            SubmissionRepository.release_or_fail,
            submission_id,
            f"{type(error).__name__}: {error}",
            SYNTHETIC_WORKER_MAX_ATTEMPTS,
        )
        if submission["processing_attempts"] >= SYNTHETIC_WORKER_MAX_ATTEMPTS:
            try:
                await bot.send_message(
                    int(ADMIN_TELEGRAM_ID),
                    "🔴 Синтетическая работа не обработана после "
                    f"{SYNTHETIC_WORKER_MAX_ATTEMPTS} попыток.\n"
                    f"Номер: {submission_id}\n"
                    "Проверьте логи Render. Работа сохранена в PostgreSQL.",
                )
            except Exception:
                logger.exception(
                    "Teacher was not notified about failed submission: %s",
                    submission_id,
                )
    return True


async def notify_next_analysis(bot: Bot) -> bool:
    notification = await asyncio.to_thread(
        SubmissionRepository.get_pending_analysis_notification
    )
    if not notification:
        return False

    await bot.send_message(
        int(ADMIN_TELEGRAM_ID),
        format_analysis_for_teacher(
            notification["submission_id"],
            notification["analysis_result"],
        ),
    )
    await asyncio.to_thread(
        SubmissionRepository.mark_analysis_notified,
        notification["submission_id"],
    )
    return True


async def run_synthetic_submission_worker(bot: Bot) -> None:
    logger.info(
        "Synthetic Gemini worker started: interval=%ss max_attempts=%s",
        SYNTHETIC_WORKER_INTERVAL_SECONDS,
        SYNTHETIC_WORKER_MAX_ATTEMPTS,
    )
    while True:
        try:
            await notify_next_analysis(bot)
            processed = await process_next_synthetic_submission(bot)
        except asyncio.CancelledError:
            raise
        except Exception:
            processed = False
            logger.exception("Synthetic Gemini worker iteration failed")

        await asyncio.sleep(
            1 if processed else SYNTHETIC_WORKER_INTERVAL_SECONDS
        )
