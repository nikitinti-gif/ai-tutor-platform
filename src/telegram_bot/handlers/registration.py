import logging

from aiogram import Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup

from config import ADMIN_TELEGRAM_ID
from src.core.roles import ROLE_STUDENT, ROLE_PARENT, ROLE_TEACHER, ROLE_NAMES
from src.repositories.ege_session_repository import EgeSessionRepository
from src.repositories.homework_repository import HomeworkRepository
from src.repositories.learning_dna_repository import LearningDNARepository
from src.repositories.user_repository import UserRepository
from src.telegram_bot.keyboards.role_menus import (
    student_menu,
    parent_menu,
    teacher_menu,
)


logger = logging.getLogger(__name__)


role_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👨‍🎓 Ученик")],
        [KeyboardButton(text="👨‍👩‍👧 Родитель")],
    ],
    resize_keyboard=True,
)


def is_admin(message: Message) -> bool:
    return bool(
        message.from_user
        and ADMIN_TELEGRAM_ID
        and str(message.from_user.id) == str(ADMIN_TELEGRAM_ID)
    )


def get_menu_by_role(role: str):
    if role == ROLE_STUDENT:
        return student_menu
    if role == ROLE_PARENT:
        return parent_menu
    if role == ROLE_TEACHER:
        return teacher_menu
    return role_menu


async def start_handler(message: Message):
    try:
        user = UserRepository.get_by_telegram_id(message.from_user.id)
        if not user and is_admin(message):
            user = UserRepository.create(
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name,
                role=ROLE_TEACHER,
            )
    except Exception:
        logger.exception("User could not be loaded during /start")
        await message.answer("🔴 Сервис регистрации временно недоступен.")
        return

    if user:
        await message.answer(
            f"С возвращением, {user['full_name']}!\n\n"
            f"Твоя роль: {ROLE_NAMES.get(user['role'])}",
            reply_markup=get_menu_by_role(user["role"]),
        )
        return

    await message.answer(
        "Привет! Я AI-платформа для подготовки к ЕГЭ/ОГЭ.\n\n"
        "Кто ты?",
        reply_markup=role_menu,
    )


async def register_student(message: Message):
    try:
        user = UserRepository.create(
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            role=ROLE_STUDENT,
        )
    except Exception:
        logger.exception("Student registration failed")
        await message.answer("🔴 Не удалось зарегистрироваться. Попробуйте позже.")
        return

    await message.answer(
        f"Готово! Ты зарегистрирован как {ROLE_NAMES[user['role']]}.\n\n"
        "Теперь тебе доступно меню ученика.",
        reply_markup=get_menu_by_role(user["role"]),
    )


async def register_parent(message: Message):
    try:
        user = UserRepository.create(
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            role=ROLE_PARENT,
        )
    except Exception:
        logger.exception("Parent registration failed")
        await message.answer("🔴 Не удалось зарегистрироваться. Попробуйте позже.")
        return

    await message.answer(
        f"Готово! Ты зарегистрирован как {ROLE_NAMES[user['role']]}.\n\n"
        "Открываю доступное меню.",
        reply_markup=get_menu_by_role(user["role"]),
    )


async def register_teacher(message: Message):
    if not is_admin(message):
        await message.answer("⛔ Регистрация преподавателя закрыта.")
        return
    try:
        user = UserRepository.create(
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            role=ROLE_TEACHER,
        )
    except Exception:
        logger.exception("Teacher registration failed")
        await message.answer("🔴 Не удалось зарегистрироваться. Попробуйте позже.")
        return

    await message.answer(
        f"Готово! Ты зарегистрирован как {ROLE_NAMES[user['role']]}.\n\n"
        "Открываю доступное меню.",
        reply_markup=get_menu_by_role(user["role"]),
    )


async def test_student(message: Message, state):
    """Reset only the admin's student data and enter the real student flow."""
    if not is_admin(message):
        await message.answer("Команда недоступна.")
        return

    telegram_id = message.from_user.id
    try:
        user = UserRepository.enter_student_test_mode(
            telegram_id, ROLE_STUDENT
        )
        if not user:
            await message.answer("Команда недоступна.")
            return
        LearningDNARepository.delete(telegram_id)
        EgeSessionRepository.delete(telegram_id)
        HomeworkRepository.delete_student_progress(telegram_id)
        await state.clear()
    except Exception:
        logger.exception("Student E2E test mode could not be enabled")
        await message.answer("🔴 Не удалось включить тестовый режим.")
        return

    await message.answer(
        "🧪 Тестовый режим ученика включён.\n"
        "Профиль очищен для нового E2E.\n"
        "Роль: student.\n\n"
        "Теперь:\n"
        "1. /start\n"
        "2. Пробный КЕГЭ 2026\n"
        "3. пройти 27 заданий\n"
        "4. открыть карту знаний\n"
        "5. начать обучение"
    )


async def restore_teacher(message: Message, state):
    """Restore the admin's captured role without deleting student results."""
    if not is_admin(message):
        await message.answer("Команда недоступна.")
        return

    try:
        user = UserRepository.restore_role(
            message.from_user.id, ROLE_TEACHER
        )
        if not user:
            await message.answer("Команда недоступна.")
            return
        await state.clear()
    except Exception:
        logger.exception("Teacher role could not be restored")
        await message.answer("🔴 Не удалось восстановить роль.")
        return

    await message.answer("👨‍🏫 Роль преподавателя восстановлена.")


def register_registration_handlers(dp: Dispatcher):
    dp.message.register(start_handler, CommandStart())
    dp.message.register(test_student, F.text == "/test_student")
    dp.message.register(restore_teacher, F.text == "/restore_teacher")
    dp.message.register(register_student, F.text == "👨‍🎓 Ученик")
    dp.message.register(register_parent, F.text == "👨‍👩‍👧 Родитель")
    dp.message.register(register_teacher, F.text == "👩‍🏫 Преподаватель")
