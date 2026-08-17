import asyncio
import logging
from io import BytesIO

from config import (
    ADMIN_TELEGRAM_ID,
    AI_DIAGNOSTIC_PROBES_ENABLED,
    QWEN_PILOT_V2_ENABLED,
)
from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import FSInputFile, Message

from src.ai_engine.homework_checker import (
    check_homework_image,
    check_homework_text,
    render_check_result_for_student,
)
from src.database.json_storage import (
    delete_ege_session,
    get_ege_session,
    save_ege_session,
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
    """Send an automatically cropped high-resolution PDF fragment."""
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
        cache_dir="cache/ege_2026_high_quality",
        pdf_url=OFFICIAL_PDF_URL,
        zoom=2.0,
    )
    task = get_open_variant_task(task_number)
    try:
        fragment_path = await asyncio.to_thread(
            service.get_fragment, task_number, page_hint=task.pdf_page
        )
        await message.answer_document(
            document=FSInputFile(
                fragment_path,
                filename=f"ege_2026_task_{task_number:02d}.png",
            ),
            caption=f"🔍 Задание {task_number} · полное качество",
        )
    except TaskFragmentError as exc:
        logger.warning("EGE PDF fragment failed for task %s: %s", task_number, exc)
        await message.answer(
            "⚠️ Не удалось подготовить изображение. Ниже отправляю текст условия."
        )

    await message.answer(render_task(task_number))


async def _complete_ege_diagnostics(
    message: Message,
    state: FSMContext,
    attempt,
) -> None:
    """Atomically persist confirmed diagnoses and finish the Telegram flow."""
    from src.learning_dna.engine import apply_confirmed_ege_diagnostics
    from src.services.ege_exam_service import diagnostic_summary

    current_dna = LearningDNARepository.get(message.from_user.id)
    dna, write_result = apply_confirmed_ege_diagnostics(
        current_dna,
        message.from_user.id,
        attempt,
    )
    from src.learning_dna.engine import set_ege_remediation_status
    from src.services.ege_exam_service import (
        render_task5_remediation,
        start_task5_remediation,
        render_task14_remediation,
        start_task14_remediation,
        render_task27_remediation,
        start_task27_remediation,
    )

    remediation = start_task5_remediation(attempt)
    if not remediation:
        remediation = start_task14_remediation(attempt)
    if not remediation:
        remediation = start_task27_remediation(attempt)
    if remediation:
        dna = set_ege_remediation_status(dna, int(remediation["task_number"]), "remediating")
    LearningDNARepository.save(message.from_user.id, dna)
    save_ege_session(
        message.from_user.id,
        attempt.to_dict(),
        status="remediation_in_progress" if remediation else "completed",
    )

    plan = dna.get("trajectory", {}).get("individual_plan", [])
    next_focus = (plan[0].get("skill_name") if plan else None) or dna.get("trajectory", {}).get("next_focus")
    lines = [
        diagnostic_summary(attempt),
        "",
        "💾 Подтверждённые результаты записаны в Learning DNA.",
        f"Новых доказательств: {write_result['applied_count']}.",
        f"Шагов в индивидуальном плане: {len(plan)}.",
    ]
    if next_focus:
        lines.append(f"🎯 Следующий фокус: {next_focus}")
    await message.answer("\n".join(lines))
    if remediation:
        await state.set_state(StudentEgeExamStates.waiting_remediation_answer)
        await state.update_data(ege_attempt=attempt.to_dict())
        renderer = {5: render_task5_remediation, 14: render_task14_remediation, 27: render_task27_remediation}[int(remediation["task_number"])]
        await message.answer(renderer(attempt, include_lesson=True))
    else:
        await state.clear()


async def receive_ege_remediation_answer(message: Message, state: FSMContext) -> None:
    from src.learning_dna.engine import (
        confirm_ege_remediation_mastery,
        set_ege_remediation_status,
    )
    from src.services.ege_exam_service import (
        ExamAttempt,
        render_task5_remediation,
        submit_task5_remediation_answer,
        start_task5_remediation,
        render_task14_remediation,
        submit_task14_remediation_answer,
        start_task14_remediation,
        render_task27_remediation,
        submit_task27_remediation_answer,
        start_task27_remediation,
    )

    data = await state.get_data()
    attempt_data = data.get("ege_attempt")
    if not attempt_data:
        saved = get_ege_session(message.from_user.id)
        attempt_data = saved.get("attempt") if saved else None
    if not attempt_data:
        await state.clear()
        await message.answer("Обучающая сессия не найдена.")
        return

    attempt = ExamAttempt.from_dict(attempt_data)
    remediation_task = int((attempt.remediation or {}).get("task_number", 14))
    submitter = {5: submit_task5_remediation_answer, 14: submit_task14_remediation_answer, 27: submit_task27_remediation_answer}[remediation_task]
    renderer = {5: render_task5_remediation, 14: render_task14_remediation, 27: render_task27_remediation}[remediation_task]
    result = submitter(attempt, message.text or "")
    dna = LearningDNARepository.get(message.from_user.id)
    if dna:
        if result["status"] == "mastered":
            dna = confirm_ege_remediation_mastery(
                dna, remediation_task, attempt.attempt_id, attempt.remediation
            )
        else:
            dna = set_ege_remediation_status(dna, remediation_task, result["status"])
        LearningDNARepository.save(message.from_user.id, dna)

    if result["status"] == "mastered":
        attempt.remediation = {}
        starters = ((5, start_task5_remediation, render_task5_remediation), (14, start_task14_remediation, render_task14_remediation), (27, start_task27_remediation, render_task27_remediation))
        next_remediation = None
        next_renderer = None
        for task_no, starter, candidate_renderer in starters:
            if task_no <= remediation_task:
                continue
            next_remediation = starter(attempt)
            if next_remediation:
                next_renderer = candidate_renderer
                break
        if next_remediation:
            next_task = int(next_remediation["task_number"])
            if dna:
                dna = set_ege_remediation_status(dna, next_task, "remediating")
                LearningDNARepository.save(message.from_user.id, dna)
            save_ege_session(message.from_user.id, attempt.to_dict(), status="remediation_in_progress")
            await state.update_data(ege_attempt=attempt.to_dict())
            await message.answer(f"✅ Навык №{remediation_task} подтверждён. Переходим к следующему доказанному пробелу — №{next_task}.")
            await message.answer(next_renderer(attempt, include_lesson=True))
            return
        save_ege_session(message.from_user.id, attempt.to_dict(), status="completed")
        await state.clear()
        next_focus = (dna or {}).get("trajectory", {}).get("next_focus")
        next_line = (
            f"\n\nСледующий шаг: {next_focus}."
            if next_focus
            else "\n\nСледующий шаг подберу по твоему профилю."
        )
        await message.answer(
            "🏆 Навык подтверждён. Ты справился с объяснением, переносом "
            "и независимой задачей без подсказки. Результат записан в "
            "Learning DNA."
            + next_line
        )
        return

    save_ege_session(
        message.from_user.id,
        attempt.to_dict(),
        status="remediation_in_progress",
    )
    await state.update_data(ege_attempt=attempt.to_dict())
    if result["status"] == "retesting":
        await message.answer(
            "✅ Правило применено верно. Теперь — новая задача без подсказки. "
            "Только после неё навык будет считаться подтверждённым."
        )
    elif result["is_correct"]:
        await message.answer(
            "✅ Верно. Теперь проверим, сможешь ли ты применить это правило "
            f"на новых данных по заданию №{remediation_task}."
        )
    elif result["stage"] == "control" and attempt.remediation.get("learning_round", 1) > 1:
        await message.answer(
            "Эта независимая задача показала, что правило пока не стало "
            "устойчивым. Это нормально: разберём его другим способом и "
            "попробуем снова на новых данных."
        )
    else:
        await message.answer("Пока неверно — ничего страшного. Посмотри на подсказку и попробуй ещё раз.")
    await message.answer(renderer(attempt))


async def _begin_ege_diagnostics(
    message: Message,
    state: FSMContext,
    attempt,
) -> None:
    from src.services.ege_exam_service import (
        bind_current_diagnostic_probe,
        diagnostic_summary,
        next_attempt_diagnostic_probe,
        render_diagnostic_probe,
    )

    await _prepare_ai_probe_for_admin(message, attempt)
    probe = bind_current_diagnostic_probe(attempt)
    if probe is None:
        await _complete_ege_diagnostics(message, state, attempt)
        return

    await message.answer(
        "Теперь разберём только ошибочные задания. Сначала проверю один "
        "конкретный навык. Если он выполнен верно, не буду искать пробел "
        "наугад — перейдём к следующему заданию. Ответ всегда проверяет Python."
    )
    probe_text = render_diagnostic_probe(attempt)
    await message.answer(probe_text)
    from src.services.ege_exam_service import mark_current_diagnostic_probe_displayed
    mark_current_diagnostic_probe_displayed(attempt)
    save_ege_session(
        message.from_user.id,
        attempt.to_dict(),
        status="diagnostics_in_progress",
    )
    await state.set_state(StudentEgeExamStates.waiting_diagnostic_answer)
    await state.update_data(ege_attempt=attempt.to_dict())


async def _prepare_ai_probe_for_admin(message: Message, attempt) -> None:
    """Best-effort live AI parameters for the isolated admin pilot."""
    if not AI_DIAGNOSTIC_PROBES_ENABLED:
        return
    if not ADMIN_TELEGRAM_ID or str(message.from_user.id) != str(ADMIN_TELEGRAM_ID):
        return
    from src.services.ege_exam_service import prepare_ai_diagnostic_probe

    try:
        await asyncio.to_thread(prepare_ai_diagnostic_probe, attempt)
    except Exception:
        logging.exception("Live AI diagnostic probe failed; using local fallback")


async def receive_ege_diagnostic_answer(
    message: Message,
    state: FSMContext,
) -> None:
    from src.services.ege_exam_service import (
        ExamAttempt,
        bind_current_diagnostic_probe,
        diagnostic_summary,
        next_attempt_diagnostic_probe,
        render_diagnostic_probe,
        submit_diagnostic_answer,
    )

    data = await state.get_data()
    attempt_data = data.get("ege_attempt")
    if not attempt_data:
        saved = get_ege_session(message.from_user.id)
        attempt_data = saved.get("attempt") if saved else None
    if not attempt_data:
        await state.clear()
        await message.answer("Диагностическая сессия не найдена. Запусти /ege2026.")
        return

    attempt = ExamAttempt.from_dict(attempt_data)
    result = submit_diagnostic_answer(
        attempt, message.text or "", student_id=message.from_user.id
    )
    save_ege_session(
        message.from_user.id,
        attempt.to_dict(),
        status="diagnostics_in_progress",
    )
    await state.update_data(ege_attempt=attempt.to_dict())

    if result["is_correct"]:
        await message.answer(
            "✅ Этот навык выполнен верно. Пробел не подтверждён, поэтому "
            "не будем искать другую слабость наугад и перейдём дальше."
        )
    elif result["status"] == "confirmed":
        diagnosis = result.get("diagnosis") or result.get("failed_step") or "Точка ошибки подтверждена."
        rule = result.get("required_rule")
        text = "🔴 Точка ошибки подтверждена двумя независимыми пробами:\n" + diagnosis
        if rule:
            text += "\n\n📌 Что нужно повторить:\n" + rule
        await message.answer(text)
    else:
        await message.answer(
            "🟡 Получено первое свидетельство ошибки. "
            "Нужна ещё одна независимая проба этого же шага."
        )

    if next_attempt_diagnostic_probe(attempt) is None:
        await _complete_ege_diagnostics(message, state, attempt)
        return

    await _prepare_ai_probe_for_admin(message, attempt)
    bind_current_diagnostic_probe(attempt)
    probe_text = render_diagnostic_probe(attempt)
    await message.answer(probe_text)
    from src.services.ege_exam_service import mark_current_diagnostic_probe_displayed
    mark_current_diagnostic_probe_displayed(attempt)
    await state.update_data(ege_attempt=attempt.to_dict())
    save_ege_session(
        message.from_user.id,
        attempt.to_dict(),
        status="diagnostics_in_progress",
    )


async def start_ege_exam(message: Message, state: FSMContext):
    from src.services.ege_exam_service import ExamAttempt

    saved = get_ege_session(message.from_user.id)
    if saved and saved.get("status") == "remediation_in_progress":
        from src.services.ege_exam_service import render_task5_remediation, render_task14_remediation, render_task27_remediation

        attempt = ExamAttempt.from_dict(saved.get("attempt"))
        task_number = int((attempt.remediation or {}).get("task_number", 14))
        renderer = {5: render_task5_remediation, 14: render_task14_remediation, 27: render_task27_remediation}[task_number]
        await state.set_state(StudentEgeExamStates.waiting_remediation_answer)
        await state.update_data(ege_attempt=attempt.to_dict())
        await message.answer(f"▶️ Продолжаем короткое обучение по заданию №{task_number}.")
        await message.answer(renderer(attempt))
        return
    if saved and saved.get("status") == "diagnostics_in_progress":
        attempt = ExamAttempt.from_dict(saved.get("attempt"))
        await _prepare_ai_probe_for_admin(message, attempt)
        from src.services.ege_exam_service import bind_current_diagnostic_probe, render_diagnostic_probe
        bind_current_diagnostic_probe(attempt)
        await message.answer("▶️ Продолжаем диагностику ошибок.")
        probe_text = render_diagnostic_probe(attempt)
        await message.answer(probe_text)
        from src.services.ege_exam_service import mark_current_diagnostic_probe_displayed
        mark_current_diagnostic_probe_displayed(attempt)
        await state.set_state(StudentEgeExamStates.waiting_diagnostic_answer)
        await state.update_data(ege_attempt=attempt.to_dict())
        save_ege_session(
            message.from_user.id,
            attempt.to_dict(),
            status="diagnostics_in_progress",
        )
        return
    if saved and saved.get("status") == "in_progress":
        attempt = ExamAttempt.from_dict(saved.get("attempt"))
        intro = f"▶️ Продолжаем вариант с задания {attempt.current_task} из 27."
    else:
        attempt = ExamAttempt()
        intro = (
            "🎓 Открытый вариант КЕГЭ-2026\n\n"
            "27 заданий. Проверка ответов локальная — без AI и расходов API."
        )
        save_ege_session(message.from_user.id, attempt.to_dict())

    await state.set_state(StudentEgeExamStates.waiting_answer)
    await state.update_data(ege_attempt=attempt.to_dict())
    await message.answer(intro)
    await _send_ege_task(message, attempt.current_task)


async def start_ege_tutor_pilot(message: Message, state: FSMContext):
    """Task-first pilot: normal EGE-like tasks before any diagnostic question."""
    is_admin = bool(
        ADMIN_TELEGRAM_ID
        and str(message.from_user.id) == str(ADMIN_TELEGRAM_ID)
    )
    if not is_admin:
        await message.answer("⛔ Эта тестовая команда доступна только администратору.")
        return
    from src.services.ege_exam_service import create_task_first_tutor_attempt, render_tutor_pilot_task

    delete_ege_session(message.from_user.id)
    await state.clear()
    attempt = create_task_first_tutor_attempt()
    await state.set_state(StudentEgeExamStates.waiting_tutor_pilot_answer)
    await state.update_data(ege_attempt=attempt.to_dict(), tutor_pilot_index=0)
    save_ege_session(message.from_user.id, attempt.to_dict(), status="tutor_pilot_in_progress")
    await message.answer(
        "🧑‍🏫 Пилот AI-репетитора · №5, №14 и №27\n\n"
        "Сейчас задания даны в учебном режиме: сначала короткое объяснение и пример, "
        "затем похожая задача для самостоятельного решения. По мере освоения навыка "
        "подсказки будут убираться, пока формулировка не станет экзаменационной.\n\n"
        "Диагностика появится только после реальной ошибки и не будет искать слабости наугад."
    )
    await message.answer(render_tutor_pilot_task(5))


async def receive_ege_tutor_pilot_answer(message: Message, state: FSMContext) -> None:
    from src.services.ege_exam_service import (
        ExamAttempt,
        record_tutor_pilot_answer,
        render_tutor_pilot_task,
    )
    data = await state.get_data()
    attempt_data = data.get("ege_attempt")
    if not attempt_data:
        await state.clear()
        await message.answer("Пилотная сессия не найдена. Запусти /test_ege_tutor.")
        return
    attempt = ExamAttempt.from_dict(attempt_data)
    tasks = (5, 14, 27)
    index = int(data.get("tutor_pilot_index", 0))
    if not 0 <= index < len(tasks):
        await state.clear()
        await message.answer("Пилотная сессия завершена. Запусти /test_ege_tutor заново.")
        return
    task_number = tasks[index]
    is_correct = record_tutor_pilot_answer(attempt, task_number, message.text or "")
    await message.answer(
        "✅ Верно." if is_correct else "❌ Ответ неверный. Сначала закончим три задания, затем разберём только реальные ошибки."
    )
    index += 1
    await state.update_data(ege_attempt=attempt.to_dict(), tutor_pilot_index=index)
    save_ege_session(message.from_user.id, attempt.to_dict(), status="tutor_pilot_in_progress")
    if index < len(tasks):
        await message.answer(render_tutor_pilot_task(tasks[index]))
        return
    if not attempt.diagnostics:
        save_ege_session(message.from_user.id, attempt.to_dict(), status="completed")
        await state.clear()
        await message.answer("🏆 Все три задания выполнены верно. Диагностика не нужна.")
        return
    await message.answer(
        "Теперь разберём только те задания, где была ошибка. "
        "Каждая диагностическая проверка будет короткой и привязанной к конкретному навыку."
    )
    await _begin_ege_diagnostics(message, state, attempt)


async def start_ege_diagnostic_pilot(message: Message, state: FSMContext):
    """Start the 5/14/27 probe review without completing the full exam."""
    is_admin = bool(
        ADMIN_TELEGRAM_ID
        and str(message.from_user.id) == str(ADMIN_TELEGRAM_ID)
    )
    if not is_admin:
        await message.answer("⛔ Эта тестовая команда доступна только администратору.")
        return

    from src.services.ege_exam_service import create_pilot_diagnostic_attempt

    delete_ege_session(message.from_user.id)
    await state.clear()
    attempt = create_pilot_diagnostic_attempt()
    await message.answer(
        "🧪 Пилот разбора ошибок №5, №14 и №27.\n\n"
        "Полный вариант проходить не нужно. Это проверка логики репетитора: "
        "не приписываем пробел без доказательств и не гоняем ученика по всем "
        "микрошагам задания."
    )
    await _begin_ege_diagnostics(message, state, attempt)


async def receive_ege_answer(message: Message, state: FSMContext):
    from src.services.ege_exam_service import (
        ExamAttempt, render_summary, submit_answer,
    )

    data = await state.get_data()
    attempt_data = data.get("ege_attempt")
    if not attempt_data:
        saved = get_ege_session(message.from_user.id)
        attempt_data = saved.get("attempt") if saved else None

    attempt = ExamAttempt.from_dict(attempt_data)
    result = submit_answer(attempt, message.text or "")

    if attempt.finished:
        await message.answer(f"{result.message}\n\n{render_summary(attempt)}")
        await _begin_ege_diagnostics(message, state, attempt)
        return

    save_ege_session(message.from_user.id, attempt.to_dict())
    await state.update_data(ege_attempt=attempt.to_dict())
    await message.answer(result.message)
    await _send_ege_task(message, attempt.current_task)


async def skip_ege_task(message: Message, state: FSMContext):
    from src.services.ege_exam_service import ExamAttempt, render_summary, skip_task

    data = await state.get_data()
    attempt_data = data.get("ege_attempt")
    if not attempt_data:
        saved = get_ege_session(message.from_user.id)
        attempt_data = saved.get("attempt") if saved else None

    attempt = ExamAttempt.from_dict(attempt_data)
    skipped_number = skip_task(attempt)

    if attempt.finished:
        await message.answer(
            f"⏭ Задание {skipped_number} пропущено.\n\n{render_summary(attempt)}"
        )
        await _begin_ege_diagnostics(message, state, attempt)
        return

    save_ege_session(message.from_user.id, attempt.to_dict())
    await state.update_data(ege_attempt=attempt.to_dict())
    await message.answer(f"⏭ Задание {skipped_number} пропущено.")
    await _send_ege_task(message, attempt.current_task)


async def finish_ege_exam(message: Message, state: FSMContext):
    from src.services.ege_exam_service import ExamAttempt, render_summary

    data = await state.get_data()
    attempt_data = data.get("ege_attempt")
    if not attempt_data:
        saved = get_ege_session(message.from_user.id)
        attempt_data = saved.get("attempt") if saved else None

    attempt = ExamAttempt.from_dict(attempt_data)
    await message.answer(render_summary(attempt))
    await _begin_ege_diagnostics(message, state, attempt)


async def cancel_ege_exam(message: Message, state: FSMContext):
    delete_ege_session(message.from_user.id)
    await state.clear()
    await message.answer("КЕГЭ-вариант отменён и удалён. Запустить заново: /ege2026")


def register_student_handlers(dp: Dispatcher):
    dp.message.register(cancel_ege_exam, F.text == "/cancel_ege")
    dp.message.register(start_ege_tutor_pilot, F.text == "/test_ege_tutor")
    dp.message.register(start_ege_diagnostic_pilot, F.text == "/test_ege_diagnostics")
    dp.message.register(receive_ege_tutor_pilot_answer, StudentEgeExamStates.waiting_tutor_pilot_answer)
    dp.message.register(skip_ege_task, StudentEgeExamStates.waiting_answer, F.text == "/skip_ege")
    dp.message.register(finish_ege_exam, StudentEgeExamStates.waiting_answer, F.text == "/finish_ege")
    dp.message.register(start_ege_exam, F.text.in_({"/ege2026", "🎓 Пройти КЕГЭ"}))
    dp.message.register(
        receive_ege_answer,
        StudentEgeExamStates.waiting_answer,
        F.text,
    )
    dp.message.register(
        receive_ege_diagnostic_answer,
        StudentEgeExamStates.waiting_diagnostic_answer,
        F.text,
    )
    dp.message.register(
        receive_ege_remediation_answer,
        StudentEgeExamStates.waiting_remediation_answer,
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
