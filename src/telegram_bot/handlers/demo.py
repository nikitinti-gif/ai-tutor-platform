import asyncio
import logging
from io import BytesIO

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

from config import ADMIN_TELEGRAM_ID
from src.ai_engine.evaluation import (
    SYNTHETIC_CASES,
    evaluate_synthetic_case,
)
from src.ai_engine.image_evaluation import (
    SYNTHETIC_IMAGE_CASES,
    evaluate_synthetic_image_case,
)
from src.ai_engine.homework_checker import (
    check_homework_image,
    render_check_result_for_student,
)
from src.repositories.learning_dna_repository import LearningDNARepository
from src.repositories.homework_repository import HomeworkRepository
from src.services.homework_service import (
    format_homework_for_student,
    generate_homework_by_topic,
)
from src.services.demo_data_service import create_informatics_demo


logger = logging.getLogger(__name__)
evaluation_tasks: set[asyncio.Task] = set()
MAX_SYNTHETIC_PHOTO_BYTES = 5 * 1024 * 1024


async def demo_informatics(message: Message):
    result = create_informatics_demo(
        user_id=message.from_user.id,
        full_name=message.from_user.full_name,
    )

    await message.answer(result)


def is_admin(message: Message) -> bool:
    return bool(
        message.from_user
        and ADMIN_TELEGRAM_ID
        and str(message.from_user.id) == str(ADMIN_TELEGRAM_ID)
    )


async def run_gemini_evaluation(bot: Bot, chat_id: int) -> None:
    matched = 0
    failed = 0
    mismatches = []

    try:
        for index, case in enumerate(SYNTHETIC_CASES, start=1):
            try:
                evaluation = await asyncio.to_thread(
                    evaluate_synthetic_case,
                    case,
                )
            except Exception as error:
                failed += 1
                logger.exception(
                    "Gemini evaluation failed for %s",
                    case["id"],
                )
                mismatches.append(
                    f"• {case['id']}: API {type(error).__name__}"
                )
            else:
                matched += int(evaluation["match"])
                if not evaluation["match"]:
                    mismatches.append(
                        f"• {case['id']}: "
                        f"{evaluation['expected']} → "
                        f"{evaluation['actual']} "
                        f"({evaluation['confidence']:.2f})"
                    )
                logger.info("Gemini evaluation result: %s", evaluation)

            if index in {5, 10}:
                await bot.send_message(
                    chat_id,
                    f"⏳ Проверено {index}/{len(SYNTHETIC_CASES)}",
                )

            await asyncio.sleep(1)

        details = "\n".join(mismatches) or "Нет."
        await bot.send_message(
            chat_id,
            "🧪 Синтетическая оценка Gemini завершена.\n\n"
            f"Примеров: {len(SYNTHETIC_CASES)}\n"
            f"Совпало с ожиданием: {matched}\n"
            f"Ошибок API: {failed}\n\n"
            f"Несовпадения и ошибки:\n{details}",
        )
    except Exception:
        logger.exception("Gemini evaluation background task crashed")
        await bot.send_message(
            chat_id,
            "🔴 Фоновая оценка Gemini прервана. Проверь логи Render.",
        )


async def start_gemini_evaluation(message: Message) -> None:
    if not is_admin(message):
        await message.answer("⛔ Команда доступна только администратору.")
        return

    if evaluation_tasks:
        await message.answer("⏳ Оценка Gemini уже выполняется.")
        return

    await message.answer(
        "🧪 Запускаю 15 синтетических примеров. "
        "Реальные данные учеников не используются."
    )
    task = asyncio.create_task(
        run_gemini_evaluation(message.bot, message.chat.id)
    )
    evaluation_tasks.add(task)
    task.add_done_callback(evaluation_tasks.discard)


async def run_gemini_image_evaluation(bot: Bot, chat_id: int) -> None:
    matched = 0
    failed = 0
    mismatches = []

    try:
        for case in SYNTHETIC_IMAGE_CASES:
            try:
                evaluation = await asyncio.to_thread(
                    evaluate_synthetic_image_case,
                    case,
                )
            except Exception as error:
                failed += 1
                logger.exception(
                    "Gemini synthetic image evaluation failed for %s",
                    case["id"],
                )
                mismatches.append(
                    f"• {case['id']}: API {type(error).__name__}"
                )
            else:
                matched += int(evaluation["match"])
                if not evaluation["match"]:
                    mismatches.append(
                        f"• {evaluation['id']}: "
                        f"{evaluation['expected']} → "
                        f"{evaluation['actual']} "
                        f"({evaluation['confidence']:.2f})"
                    )
                logger.info(
                    "Gemini synthetic image evaluation result: %s",
                    evaluation,
                )

            await asyncio.sleep(1)

        details = "\n".join(mismatches) or "Нет."
        await bot.send_message(
            chat_id,
            "🖼 Синтетическая оценка изображений завершена.\n\n"
            f"Примеров: {len(SYNTHETIC_IMAGE_CASES)}\n"
            f"Совпало с ожиданием: {matched}\n"
            f"Ошибок API: {failed}\n\n"
            f"Несовпадения и ошибки:\n{details}",
        )
    except Exception:
        logger.exception("Gemini synthetic image evaluation task crashed")
        await bot.send_message(
            chat_id,
            "🔴 Оценка синтетических изображений прервана. "
            "Проверь логи Render.",
        )


async def start_gemini_image_evaluation(message: Message) -> None:
    if not is_admin(message):
        await message.answer("⛔ Команда доступна только администратору.")
        return

    if evaluation_tasks:
        await message.answer("⏳ Другая оценка Gemini уже выполняется.")
        return

    await message.answer(
        "🖼 Отправляю Gemini 5 синтетических изображений решений. "
        "Реальные фотографии учеников не используются."
    )
    task = asyncio.create_task(
        run_gemini_image_evaluation(message.bot, message.chat.id)
    )
    evaluation_tasks.add(task)
    task.add_done_callback(evaluation_tasks.discard)


def parse_synthetic_photo_task(caption: str | None) -> str | None:
    if not caption:
        return None

    parts = caption.strip().split(maxsplit=1)
    command = parts[0].split("@", maxsplit=1)[0]

    if command != "/check_synthetic_photo" or len(parts) < 2:
        return None

    task_text = parts[1].strip()
    return task_text or None


async def run_uploaded_synthetic_photo_check(
    bot: Bot,
    chat_id: int,
    image_bytes: bytes,
    task_text: str,
) -> None:
    try:
        result = await asyncio.to_thread(
            check_homework_image,
            image_bytes=image_bytes,
            mime_type="image/jpeg",
            task_text=task_text,
            topic="Информатика",
            synthetic_test=True,
        )
        logger.info(
            "Admin synthetic photo check: status=%s legibility=%s",
            result["status"],
            result.get("image_legibility"),
        )

        try:
            saved_record = await asyncio.to_thread(
                LearningDNARepository.save_synthetic_check,
                result,
            )
        except Exception:
            logger.exception("Synthetic learning result was not saved")
            storage_message = (
                "⚠️ Структурированный результат не сохранён. "
                "Проверь логи Render."
            )
        else:
            stored_checks = await asyncio.to_thread(
                LearningDNARepository.get_synthetic_checks,
            )
            storage_message = (
                "💾 Сохранено по политике v1: "
                f"topic={saved_record['topic']}, "
                f"status={saved_record['status']}, "
                f"confidence={saved_record['confidence']:.2f}, "
                f"error_type={saved_record['error_type']}. "
                f"Записей в тестовом журнале: {len(stored_checks)}."
            )

        transcription = result.get("image_transcription") or "—"
        await bot.send_message(
            chat_id,
            "🖼 Проверка загруженного синтетического фото завершена.\n\n"
            f"Читаемость: {result.get('image_legibility', 'unknown')}\n"
            f"Транскрипция:\n{transcription}\n\n"
            f"{render_check_result_for_student(result)}\n\n"
            f"{storage_message}",
        )
    except Exception as error:
        logger.exception("Admin synthetic photo check failed")
        await bot.send_message(
            chat_id,
            "🔴 Проверка синтетического фото завершилась ошибкой: "
            f"{type(error).__name__}. Проверь логи Render.",
        )


async def check_uploaded_synthetic_photo(message: Message) -> None:
    if not is_admin(message):
        await message.answer("⛔ Команда доступна только администратору.")
        return

    task_text = parse_synthetic_photo_task(message.caption)
    if not task_text:
        await message.answer(
            "Добавь к фото подпись:\n"
            "/check_synthetic_photo текст задания"
        )
        return

    if evaluation_tasks:
        await message.answer("⏳ Другая оценка Gemini уже выполняется.")
        return

    photo = message.photo[-1]
    if photo.file_size and photo.file_size > MAX_SYNTHETIC_PHOTO_BYTES:
        await message.answer("⛔ Фото должно быть не больше 5 Мбайт.")
        return

    buffer = BytesIO()
    try:
        await message.bot.download(photo, destination=buffer)
        image_bytes = buffer.getvalue()
    finally:
        buffer.close()

    if not image_bytes:
        await message.answer("🔴 Telegram вернул пустой файл изображения.")
        return

    await message.answer(
        "🧪 Принято как синтетическое тестовое фото. "
        "Обрабатываю в памяти без сохранения файла."
    )
    task = asyncio.create_task(
        run_uploaded_synthetic_photo_check(
            message.bot,
            message.chat.id,
            image_bytes,
            task_text,
        )
    )
    evaluation_tasks.add(task)
    task.add_done_callback(evaluation_tasks.discard)

async def create_synthetic_student_cycle(message: Message) -> None:
    if not is_admin(message):
        await message.answer(
            "⛔ Команда доступна только администратору."
        )
        return

    topic = "Условные операторы"
    homework_data = generate_homework_by_topic(topic)

    homework = HomeworkRepository.create(
        topic=topic,
        homework_data=homework_data,
        teacher_id=message.from_user.id,
    )
    assignment = HomeworkRepository.assign_to_student(
        homework_id=homework["homework_id"],
        student_id=message.from_user.id,
    )

    await message.answer(
        "🧪 Создан новый синтетический ученический цикл.\n\n"
        f"{format_homework_for_student(homework_data)}\n\n"
        f"Статус: {assignment['status']}\n\n"
        "Теперь отправь: 📸 Проверить решение"
    )

def register_demo_handlers(dp: Dispatcher):
    dp.message.register(
        create_synthetic_student_cycle,
        Command("student_cycle_demo"),
    )
    dp.message.register(start_gemini_evaluation, Command("gemini_eval"))
    dp.message.register(
        start_gemini_image_evaluation,
        Command("gemini_image_eval"),
    )
    dp.message.register(
        check_uploaded_synthetic_photo,
        F.photo,
        F.caption.startswith("/check_synthetic_photo"),
    )
    dp.message.register(demo_informatics, Command("demo_informatics"))
