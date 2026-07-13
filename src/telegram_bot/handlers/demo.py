import asyncio
import logging

from aiogram import Bot, Dispatcher
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
from src.services.demo_data_service import create_informatics_demo


logger = logging.getLogger(__name__)
evaluation_tasks: set[asyncio.Task] = set()


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


def register_demo_handlers(dp: Dispatcher):
    dp.message.register(start_gemini_evaluation, Command("gemini_eval"))
    dp.message.register(
        start_gemini_image_evaluation,
        Command("gemini_image_eval"),
    )
    dp.message.register(demo_informatics, Command("demo_informatics"))
