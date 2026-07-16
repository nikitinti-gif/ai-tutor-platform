import asyncio
import logging
from io import BytesIO

from config import ADMIN_TELEGRAM_ID, QWEN_PILOT_V2_ENABLED
from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.ai_engine.homework_checker import (
    check_homework_image,
    check_homework_text,
    render_check_result_for_student,
)
from src.learning_dna.engine import update_learning_dna_after_check
from src.pedagogy.engine import make_pedagogical_decision
from src.repositories.homework_repository import HomeworkRepository
from src.repositories.learning_dna_repository import LearningDNARepository
from src.repositories.pedagogical_decision_repository import (
    PedagogicalDecisionRepository,
)
from src.services.homework_service import format_homework_for_student
from src.telegram_bot.states.student_states import StudentHomeworkCheckStates
from src.services.ai_teacher_service import generate_ai_teacher_feedback


logger = logging.getLogger(__name__)
MAX_PILOT_PHOTO_BYTES = 5 * 1024 * 1024


async def student_homework(message: Message):
    assignments = HomeworkRepository.get_student_assignments(
        student_id=message.from_user.id
    )

    if not assignments:
        await message.answer("📚 Пока домашних заданий нет.")
        return

    active_homework = HomeworkRepository.get_active()
    homework_by_id = {
        homework["homework_id"]: homework
        for homework in active_homework
    }

    text = "📚 Мои домашние задания:\n\n"

    for index, assignment in enumerate(assignments, start=1):
        if assignment["status"] == "new":
            assignment = HomeworkRepository.mark_as_opened(
                assignment["student_homework_id"]
            )

        homework = homework_by_id.get(assignment["homework_id"])

        if not homework:
            continue

        text += (
            f"{index}. {homework['topic']}\n"
            f"Статус: {assignment['status']}\n\n"
        )
        text += format_homework_for_student(homework["homework_data"])
        text += "\n\n"

    await message.answer(text)


async def student_photo_check(message: Message, state: FSMContext):
    await state.set_state(StudentHomeworkCheckStates.waiting_solution_text)

    await message.answer(
        "📸 Проверка решения\n\n"
        "Отправь фото решения или напиши решение текстом.\n\n"
        "Фото будет передано внешнему AI только для черновика, "
        "а окончательное решение примет преподаватель."
    )


async def student_receive_solution_photo(message: Message, state: FSMContext):
    if not QWEN_PILOT_V2_ENABLED:
        await state.clear()
        await message.answer(
            "🔒 Пилотная проверка фото сейчас выключена. "
            "Решение нужно передать преподавателю."
        )
        return

    latest_assignment = HomeworkRepository.get_latest_for_student(
        student_id=message.from_user.id
    )

    if not latest_assignment:
        await state.clear()
        await message.answer("Сначала открой домашнее задание.")
        return

    homework = next(
        (
            item
            for item in HomeworkRepository.get_active()
            if item["homework_id"] == latest_assignment["homework_id"]
        ),
        None,
    )
    if not homework:
        await state.clear()
        await message.answer("Не удалось найти активное задание.")
        return

    photo = message.photo[-1]
    if photo.file_size and photo.file_size > MAX_PILOT_PHOTO_BYTES:
        await state.clear()
        await message.answer("⛔ Фото должно быть не больше 5 Мбайт.")
        return

    HomeworkRepository.mark_as_submitted(
        latest_assignment["student_homework_id"]
    )
    buffer = BytesIO()
    try:
        await message.bot.download(photo, destination=buffer)
        image_bytes = buffer.getvalue()
    finally:
        buffer.close()

    try:
        result = await asyncio.to_thread(
            check_homework_image,
            image_bytes=image_bytes,
            mime_type="image/jpeg",
            task_text=format_homework_for_student(
                homework["homework_data"]
            ),
            topic=homework["topic"],
            provider_name="qwen",
            pilot_v2=True,
        )
        await message.bot.send_photo(
            chat_id=int(ADMIN_TELEGRAM_ID),
            photo=photo.file_id,
            caption=(
                "🧑‍🏫 Пилот v2: требуется проверка преподавателя\n"
                f"Тема: {homework['topic']}\n"
                "Имя и Telegram ID программно в запрос AI не добавлялись."
            ),
        )
        await message.bot.send_message(
            chat_id=int(ADMIN_TELEGRAM_ID),
            text=(
                "Черновик Qwen — не отправлен ученику:\n\n"
                f"{render_check_result_for_student(result)}"
            ),
        )
    except Exception:
        logger.exception("Qwen pilot v2 photo check failed")
        await message.answer(
            "🔴 Не удалось подготовить черновик проверки. "
            "Фото нужно проверить преподавателю вручную."
        )
    else:
        await message.answer(
            "✅ Фото принято. AI подготовил черновик, но не вынес "
            "окончательное решение. Преподаватель получил фото и "
            "проверит результат."
        )
    finally:
        await state.clear()


async def student_receive_solution_text(
    message: Message,
    state: FSMContext,
):
    solution_text = message.text.strip()

    if len(solution_text) < 3:
        await message.answer("Напиши решение подробнее.")
        return

    is_synthetic_admin = bool(
        ADMIN_TELEGRAM_ID
        and str(message.from_user.id) == str(ADMIN_TELEGRAM_ID)
    )

    if not is_synthetic_admin:
        await state.clear()
        await message.answer(
            "🔒 Реальная AI-проверка учеников пока не открыта. "
            "Решение передано преподавателю."
        )
        return

    latest_assignment = HomeworkRepository.get_latest_for_student(
        student_id=message.from_user.id
    )

    if not latest_assignment:
        await state.clear()
        await message.answer(
            "Сначала создай синтетическое задание командой "
            "/demo_informatics."
        )
        return

    homework = next(
        (
            item
            for item in HomeworkRepository.get_active()
            if item["homework_id"] == latest_assignment["homework_id"]
        ),
        None,
    )

    if not homework:
        await state.clear()
        await message.answer("Не удалось найти активное задание.")
        return

    HomeworkRepository.mark_as_submitted(
        latest_assignment["student_homework_id"]
    )

    task_text = format_homework_for_student(
        homework["homework_data"]
    )
    topic = homework["topic"]

    result = check_homework_text(
        solution_text,
        task_text=task_text,
        topic=topic,
        synthetic_test=True,
    )
    result["topic"] = topic

    saved_record = LearningDNARepository.save_synthetic_check(result)

    HomeworkRepository.mark_as_checked(
        student_homework_id=latest_assignment["student_homework_id"],
        check_result=result,
    )

    stored_checks = LearningDNARepository.get_synthetic_checks()

    await state.clear()
    await message.answer(
        f"{render_check_result_for_student(result)}\n\n"
        "💾 Сохранено по политике v1: "
        f"topic={saved_record['topic']}, "
        f"status={saved_record['status']}, "
        f"confidence={saved_record['confidence']:.2f}, "
        f"error_type={saved_record['error_type']}. "
        f"Записей в тестовом журнале: {len(stored_checks)}."
    )


async def student_progress(message: Message):
    await message.answer(
        "📊 Мой прогресс\n\n"
        "Скоро здесь появится карта тем: 🟢 🟡 🔴"
    )


async def student_question(message: Message):
    await message.answer(
        "❓ Напиши вопрос по заданию или теме."
    )


def register_student_handlers(dp: Dispatcher):
    dp.message.register(student_homework, F.text == "📚 Моё ДЗ")
    dp.message.register(student_photo_check, F.text == "📸 Проверить решение")
    dp.message.register(
        student_receive_solution_photo,
        StudentHomeworkCheckStates.waiting_solution_text,
        F.photo,
    )
    dp.message.register(
        student_receive_solution_text,
        StudentHomeworkCheckStates.waiting_solution_text,
        F.text,
    )
    dp.message.register(student_progress, F.text == "📊 Мой прогресс")
    dp.message.register(student_question, F.text == "❓ Задать вопрос")
