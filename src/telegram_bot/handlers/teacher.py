from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.core.roles import ROLE_STUDENT
from src.repositories.user_repository import UserRepository
from src.repositories.homework_repository import HomeworkRepository
from src.services.homework_service import (
    generate_homework_by_topic,
    format_homework_for_student,
)
from src.telegram_bot.states.student_states import TeacherHomeworkStates
from src.services.assignment_service import assign_homework_to_all_students
from src.services.teacher_dashboard_service import (
    generate_teacher_dashboard,
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
    await message.answer(
        "📸 Проверки ИИ\n\n"
        "Здесь будут ответы, которые требуют ручной проверки."
    )


async def teacher_week_summary(message: Message):
    await message.answer(
        "📊 Сводка недели\n\n"
        "Здесь будет аналитика по ученикам и темам."
    )


def register_teacher_handlers(dp: Dispatcher):
    dp.message.register(teacher_students, F.text == "👨‍🎓 Ученики")
    dp.message.register(teacher_assign_homework, F.text == "📚 Выдать ДЗ")
    dp.message.register(teacher_receive_homework_topic,TeacherHomeworkStates.waiting_homework_topic,)
    dp.message.register(teacher_ai_checks, F.text == "📸 Проверки ИИ")
    dp.message.register(teacher_week_summary, F.text == "📊 Сводка недели")
    dp.message.register(teacher_homework_status, F.text == "📊 Статус домашнего задания")

async def teacher_homework_status(message: Message):
    report = generate_teacher_dashboard()
    await message.answer(report)