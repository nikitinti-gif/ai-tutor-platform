import os

from config import ADMIN_TELEGRAM_ID
from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.ai_engine.homework_checker import (
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
from src.services.vision_service import VisionService
from src.services.ai_teacher_service import generate_ai_teacher_feedback


UPLOAD_DIR = "uploads/homework_photos"


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
        "Пока фото только сохраняется, OCR подключим следующим шагом."
    )


async def student_receive_solution_photo(message: Message, state: FSMContext):
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    latest_assignment = HomeworkRepository.get_latest_for_student(
        student_id=message.from_user.id
    )

    if latest_assignment:
        HomeworkRepository.mark_as_submitted(
            latest_assignment["student_homework_id"]
        )

    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)

    file_path = os.path.join(
        UPLOAD_DIR,
        f"{message.from_user.id}_{photo.file_unique_id}.jpg"
    )

    await message.bot.download_file(file.file_path, file_path)
    vision_result = VisionService().analyze_homework_photo(file_path)

    await state.clear()

    await message.answer(
    "✅ Фото решения получено и обработано.\n\n"
    f"Provider: {vision_result.provider}\n"
    f"Confidence: {vision_result.confidence}\n\n"
    f"Распознанный текст:\n{vision_result.text}"
    )


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