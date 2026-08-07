import asyncio
import logging

from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.ai_engine.ege_open_variant_2026 import get_open_variant_task
from src.database.json_storage import get_ege_session
from src.services.ai_teacher_service import generate_ege_hint
from src.services.ege_exam_service import ExamAttempt
from src.telegram_bot.states.student_states import StudentEgeExamStates


logger = logging.getLogger(__name__)


def _fallback_hint(task_number: int, attachment_required: bool) -> str:
    if attachment_required:
        return (
            "Сначала открой файл варианта и выпиши только те строки, "
            "которые одновременно подходят под все условия задания. "
            "Какое условие можно проверить первым?"
        )

    return (
        f"Для задания №{task_number} сначала выдели входные данные и то, "
        "что требуется получить. Какой самый простой промежуточный шаг "
        "можно выполнить без вычисления итогового ответа?"
    )


async def send_ege_hint(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    attempt_data = data.get("ege_attempt")

    if not attempt_data:
        saved = get_ege_session(message.from_user.id)
        attempt_data = saved.get("attempt") if saved else None

    if not attempt_data:
        await message.answer(
            "Сначала запусти вариант командой /ege2026."
        )
        return

    attempt = ExamAttempt.from_dict(attempt_data)
    if attempt.finished:
        await message.answer("Вариант уже завершён.")
        return

    task = get_open_variant_task(attempt.current_task)
    await message.answer("💭 Готовлю короткую подсказку без готового ответа...")

    try:
        hint = await asyncio.to_thread(
            generate_ege_hint,
            task_number=attempt.current_task,
            topic=task.title,
            statement=task.statement,
            answer_prompt=task.prompt,
        )
    except Exception as error:
        logger.warning(
            "Free EGE hint failed for task %s: %s",
            attempt.current_task,
            error,
        )
        hint = _fallback_hint(
            attempt.current_task,
            task.attachment_required,
        )
        source = "локальная резервная подсказка"
    else:
        source = "Gemini Free"

    await message.answer(
        f"💡 Подсказка к заданию {attempt.current_task}\n\n"
        f"{hint}\n\n"
        f"Источник: {source}. Итоговый ответ не раскрывается."
    )


def register_ege_hint_handlers(dp: Dispatcher) -> None:
    dp.message.register(
        send_ege_hint,
        StudentEgeExamStates.waiting_answer,
        F.text == "/hint_ege",
    )
