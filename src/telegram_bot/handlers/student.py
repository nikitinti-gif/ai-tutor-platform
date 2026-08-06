import asyncio
import logging
from io import BytesIO

from config import ADMIN_TELEGRAM_ID, QWEN_PILOT_V2_ENABLED
from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message

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
from src.telegram_bot.states.student_states import StudentHomeworkCheckStates, StudentEgeExamStates
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


async def _send_ege_task(message: Message, task_number: int) -> None:
    """Send an automatically cropped PDF fragment and the text prompt."""
    from src.ai_engine.ege_open_variant_2026 import (
        OFFICIAL_PDF_URL,
        get_open_variant_task,
    )
    from src.services.ege_exam_service import render_task
    from src.services.pdf_task_fragment_service import (
        PdfTaskFragmentService,
        TaskFragmentError,
    )

    service = PdfTaskFragmentService(
        pdf_path="assets/ege_2026/variant.pdf",
        cache_dir="cache/ege_2026",
        pdf_url=OFFICIAL_PDF_URL,
    )
    task = get_open_variant_task(task_number)
    try:
        fragment_path = await asyncio.to_thread(
            service.get_fragment, task_number, page_hint=task.pdf_page
        )
        await message.answer_photo(
            photo=FSInputFile(fragment_path),
            caption=f"🖼 Фрагмент задания {task_number}",
        )
    except TaskFragmentError as exc:
        logger.warning("EGE PDF fragment failed for task %s: %s", task_number, exc)
        await message.answer(
            "⚠️ Не удалось автоматически подготовить изображение задания. "
            "Ниже отправляю текст условия."
        )

    await message.answer(render_task(task_number))


async def start_ege_exam(message: Message, state: FSMContext):
    from src.services.ege_exam_service import ExamAttempt, render_task

    attempt = ExamAttempt()
    await state.set_state(StudentEgeExamStates.waiting_answer)
    await state.update_data(ege_attempt=attempt.to_dict())
    await message.answer(
        "🎓 Открытый вариант КЕГЭ-2026\n\n"
        "27 заданий, проверка кратких ответов без AI и без списания API."
    )
    await _send_ege_task(message, 1)


async def receive_ege_answer(message: Message, state: FSMContext):
    from src.services.ege_exam_service import (
        ExamAttempt, render_summary, render_task, submit_answer,
    )

    data = await state.get_data()
    attempt = ExamAttempt.from_dict(data.get("ege_attempt"))
    result = submit_answer(attempt, message.text or "")

    if attempt.finished:
        await state.clear()
        await message.answer(f"{result.message}\n\n{render_summary(attempt)}")
        return

    await state.update_data(ege_attempt=attempt.to_dict())
    await message.answer(result.message)
    await _send_ege_task(message, attempt.current_task)


async def skip_ege_task(message: Message, state: FSMContext):
    from src.services.ege_exam_service import ExamAttempt, render_summary, render_task, skip_task
    data = await state.get_data()
    attempt = ExamAttempt.from_dict(data.get("ege_attempt"))
    skipped_number = skip_task(attempt)
    if attempt.finished:
        await state.clear()
        await message.answer(f"⏭ Задание {skipped_number} пропущено.\n\n{render_summary(attempt)}")
        return
    await state.update_data(ege_attempt=attempt.to_dict())
    await message.answer(f"⏭ Задание {skipped_number} пропущено.")
    await _send_ege_task(message, attempt.current_task)


async def finish_ege_exam(message: Message, state: FSMContext):
    from src.services.ege_exam_service import ExamAttempt, render_summary
    data = await state.get_data()
    attempt = ExamAttempt.from_dict(data.get("ege_attempt"))
    await state.clear()
    await message.answer(render_summary(attempt))


async def cancel_ege_exam(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("КЕГЭ-вариант отменён без сохранения. Запустить заново: /ege2026")


def register_student_handlers(dp: Dispatcher):
    dp.message.register(cancel_ege_exam, F.text == "/cancel_ege")
    dp.message.register(skip_ege_task, StudentEgeExamStates.waiting_answer, F.text == "/skip_ege")
    dp.message.register(finish_ege_exam, StudentEgeExamStates.waiting_answer, F.text == "/finish_ege")
    dp.message.register(start_ege_exam, F.text.in_({"/ege2026", "🎓 Пройти КЕГЭ"}))
    dp.message.register(
        receive_ege_answer,
        StudentEgeExamStates.waiting_answer,
        F.text,
    )
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
