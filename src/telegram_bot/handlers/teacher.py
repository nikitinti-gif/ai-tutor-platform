import asyncio

from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import ADMIN_TELEGRAM_ID
from src.core.roles import ROLE_STUDENT, ROLE_TEACHER
from src.repositories.family_link_repository import FamilyLinkRepository
from src.repositories.submission_repository import SubmissionRepository
from src.repositories.user_repository import UserRepository
from src.repositories.homework_repository import HomeworkRepository
from src.services.homework_service import (
    generate_homework_by_topic,
    format_homework_for_student,
)
from src.services.family_link_service import (
    generate_link_code,
    hash_link_code,
    make_synthetic_student_id,
)
from src.telegram_bot.states.student_states import (
    ParentFamilyLinkStates,
    TeacherFamilyLinkStates,
    TeacherHomeworkStates,
    TeacherSubmissionReviewStates,
)
from src.services.assignment_service import assign_homework_to_all_students
from src.services.teacher_dashboard_service import (
    generate_teacher_dashboard,
)
from src.services.teacher_submission_queue_service import (
    format_teacher_submission_detail,
    format_teacher_submission_queue,
)


async def teacher_students(message: Message):
    students = UserRepository.get_by_role(ROLE_STUDENT)

    if not students:
        await message.answer("👨‍🎓 Пока нет зарегистрированных учеников.")
        return

    text = "👨‍🎓 Список учеников:\n\n"

    for index, student in enumerate(students, start=1):
        text += f"{index}. {student['full_name']} — Telegram ID: {student['telegram_id']}\n"

    await message.answer(text)


def is_admin(message: Message) -> bool:
    return bool(
        message.from_user
        and ADMIN_TELEGRAM_ID
        and str(message.from_user.id) == str(ADMIN_TELEGRAM_ID)
    )


async def admin_start_synthetic_family(
    message: Message,
    state: FSMContext,
):
    if not is_admin(message):
        await message.answer("⛔ Пилотный режим доступен только администратору.")
        return

    code = generate_link_code()
    synthetic_student_id = make_synthetic_student_id(message.from_user.id)
    try:
        await asyncio.to_thread(
            FamilyLinkRepository.save_code,
            hash_link_code(code),
            synthetic_student_id,
            message.from_user.id,
        )
    except Exception:
        await message.answer(
            "🔴 Не удалось создать тестовую семью. Попробуйте позже."
        )
        return

    await state.set_state(ParentFamilyLinkStates.waiting_link_code)
    await message.answer(
        "🧪 Создан синтетический ученик.\n\n"
        f"Одноразовый код: {code}\n\n"
        "Отправьте этот код следующим сообщением. Он действует 30 минут "
        "и будет использован только один раз."
    )


async def teacher_start_family_link(message: Message, state: FSMContext):
    teacher = UserRepository.get_by_telegram_id(message.from_user.id)
    if not teacher or teacher.get("role") != ROLE_TEACHER:
        await message.answer("⛔ Команда доступна только преподавателю.")
        return

    await state.set_state(TeacherFamilyLinkStates.waiting_student_id)
    await message.answer(
        "🔗 Введите Telegram ID ученика из списка «👨‍🎓 Ученики».\n\n"
        "Одноразовый код будет действовать 30 минут."
    )


async def teacher_create_family_link_code(
    message: Message,
    state: FSMContext,
):
    try:
        student_id = int(message.text.strip())
    except (TypeError, ValueError):
        await message.answer("Введите числовой Telegram ID ученика.")
        return

    student = UserRepository.get_by_telegram_id(student_id)
    if not student or student.get("role") != ROLE_STUDENT:
        await message.answer(
            "Ученик с таким Telegram ID не зарегистрирован. "
            "Проверьте список учеников."
        )
        return

    code = generate_link_code()
    try:
        await asyncio.to_thread(
            FamilyLinkRepository.save_code,
            hash_link_code(code),
            student_id,
            message.from_user.id,
        )
    except Exception:
        await message.answer(
            "🔴 Не удалось создать код. Попробуйте через несколько минут."
        )
        return

    await state.clear()
    await message.answer(
        "✅ Одноразовый код для родителя создан.\n\n"
        f"Ученик: {student['full_name']}\n"
        f"Код: {code}\n"
        "Срок действия: 30 минут.\n\n"
        "Передайте код родителю безопасным способом. После первого "
        "использования код станет недействительным."
    )


async def teacher_assign_homework(message: Message, state: FSMContext):
    await state.set_state(TeacherHomeworkStates.waiting_homework_topic)

    await message.answer(
        "📚 Выдать ДЗ\n\n"
        "Введите тему, по которой нужно создать домашнее задание.\n\n"
        "Например:\n"
        "Квадратные уравнения\n"
        "Проценты\n"
        "Задание 5 ОГЭ"
    )


async def teacher_receive_homework_topic(message: Message, state: FSMContext):
    topic = message.text.strip()

    if len(topic) < 3:
        await message.answer("Тема слишком короткая. Введите тему подробнее.")
        return

    homework_data = generate_homework_by_topic(topic)

    homework = HomeworkRepository.create(
        topic=topic,
        homework_data=homework_data,
        teacher_id=message.from_user.id,
    )

    assignments = assign_homework_to_all_students(homework["homework_id"])

    preview_text = format_homework_for_student(homework_data)

    await state.clear()

    await message.answer(
         "✅ Домашнее задание создано и назначено ученикам.\n\n"
        f"Назначено ученикам: {len(assignments)}\n\n"
        f"{preview_text}"
    )


async def teacher_ai_checks(message: Message):
    teacher = UserRepository.get_by_telegram_id(message.from_user.id)
    if (
        not teacher or teacher.get("role") != ROLE_TEACHER
    ) and not is_admin(message):
        await message.answer("⛔ Очередь доступна только преподавателю.")
        return

    try:
        submissions = await asyncio.to_thread(
            SubmissionRepository.list_for_teacher,
            10,
        )
    except Exception:
        await message.answer(
            "🔴 Не удалось загрузить очередь. Попробуйте через несколько минут."
        )
        return

    await message.answer(format_teacher_submission_queue(submissions))


async def teacher_start_submission_review(
    message: Message,
    state: FSMContext,
):
    teacher = UserRepository.get_by_telegram_id(message.from_user.id)
    if (
        not teacher or teacher.get("role") != ROLE_TEACHER
    ) and not is_admin(message):
        await message.answer("⛔ Карточки доступны только преподавателю.")
        return

    await state.set_state(TeacherSubmissionReviewStates.waiting_submission_id)
    await message.answer(
        "🔎 Отправьте номер работы, например:\n"
        "sub_15ef2c33ad48"
    )


async def teacher_open_submission(
    message: Message,
    state: FSMContext,
):
    submission_id = (message.text or "").strip()
    if not submission_id.startswith("sub_") or len(submission_id) > 64:
        await message.answer("Неверный формат номера работы. Попробуйте снова.")
        return

    try:
        submission = await asyncio.to_thread(
            SubmissionRepository.get_for_teacher,
            submission_id,
        )
    except Exception:
        await message.answer("🔴 Не удалось загрузить работу. Попробуйте позже.")
        return
    if not submission:
        await message.answer("Работа с таким номером не найдена.")
        return

    await state.clear()
    await message.bot.send_photo(
        chat_id=message.chat.id,
        photo=submission["telegram_file_id"],
        caption=f"📄 Работа {submission_id}",
    )

    keyboard = None
    if submission.get("status") != "completed":
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(
                text="✅ Завершить проверку",
                callback_data=f"complete_submission:{submission_id}",
            )]]
        )
    await message.answer(
        format_teacher_submission_detail(submission),
        reply_markup=keyboard,
    )


async def teacher_complete_submission(callback: CallbackQuery):
    user = UserRepository.get_by_telegram_id(callback.from_user.id)
    callback_is_admin = bool(
        ADMIN_TELEGRAM_ID
        and str(callback.from_user.id) == str(ADMIN_TELEGRAM_ID)
    )
    if (not user or user.get("role") != ROLE_TEACHER) and not callback_is_admin:
        await callback.answer("Недостаточно прав.", show_alert=True)
        return

    submission_id = callback.data.split(":", maxsplit=1)[1]
    try:
        completed = await asyncio.to_thread(
            SubmissionRepository.complete,
            submission_id,
        )
    except Exception:
        await callback.answer("Ошибка сохранения.", show_alert=True)
        return

    if not completed:
        await callback.answer(
            "Работу нельзя завершить в текущем статусе.",
            show_alert=True,
        )
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Проверка завершена.")
    await callback.message.answer(
        f"✅ Работа {submission_id} переведена в статус completed."
    )


async def teacher_week_summary(message: Message):
    await message.answer(
        "📊 Сводка недели\n\n"
        "Здесь будет аналитика по ученикам и темам."
    )


def register_teacher_handlers(dp: Dispatcher):
    dp.message.register(
        admin_start_synthetic_family,
        F.text == "🧪 Тестовая семья",
    )
    dp.message.register(teacher_students, F.text == "👨‍🎓 Ученики")
    dp.message.register(
        teacher_start_family_link,
        F.text == "🔗 Код для родителя",
    )
    dp.message.register(
        teacher_create_family_link_code,
        TeacherFamilyLinkStates.waiting_student_id,
        F.text,
    )
    dp.message.register(teacher_assign_homework, F.text == "📚 Выдать ДЗ")
    dp.message.register(teacher_receive_homework_topic,TeacherHomeworkStates.waiting_homework_topic,)
    dp.message.register(teacher_ai_checks, F.text == "📸 Проверки ИИ")
    dp.message.register(
        teacher_start_submission_review,
        F.text == "🔎 Открыть работу",
    )
    dp.message.register(
        teacher_open_submission,
        TeacherSubmissionReviewStates.waiting_submission_id,
        F.text,
    )
    dp.callback_query.register(
        teacher_complete_submission,
        F.data.startswith("complete_submission:"),
    )
    dp.message.register(teacher_week_summary, F.text == "📊 Сводка недели")
    dp.message.register(teacher_homework_status, F.text == "📊 Статус домашнего задания")

async def teacher_homework_status(message: Message):
    report = generate_teacher_dashboard()
    await message.answer(report)
