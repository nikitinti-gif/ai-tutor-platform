from aiogram import Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, KeyboardButton, ReplyKeyboardMarkup

from src.core.roles import ROLE_STUDENT, ROLE_PARENT, ROLE_TEACHER, ROLE_NAMES
from src.repositories.user_repository import UserRepository
from src.telegram_bot.keyboards.role_menus import (
    student_menu,
    parent_menu,
    teacher_menu,
)


role_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👨‍🎓 Ученик")],
        [KeyboardButton(text="👨‍👩‍👧 Родитель")],
        [KeyboardButton(text="👩‍🏫 Преподаватель")],
    ],
    resize_keyboard=True,
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
    user = UserRepository.get_by_telegram_id(message.from_user.id)

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
    user = UserRepository.create(
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        role=ROLE_STUDENT,
    )

    await message.answer(
        f"Готово! Ты зарегистрирован как {ROLE_NAMES[user['role']]}.\n\n"
        "Теперь тебе доступно меню ученика.",
        reply_markup=student_menu,
    )


async def register_parent(message: Message):
    user = UserRepository.create(
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        role=ROLE_PARENT,
    )

    await message.answer(
        f"Готово! Ты зарегистрирован как {ROLE_NAMES[user['role']]}.\n\n"
        "Теперь тебе доступно меню родителя.",
        reply_markup=parent_menu,
    )


async def register_teacher(message: Message):
    user = UserRepository.create(
        telegram_id=message.from_user.id,
        full_name=message.from_user.full_name,
        role=ROLE_TEACHER,
    )

    await message.answer(
        f"Готово! Ты зарегистрирован как {ROLE_NAMES[user['role']]}.\n\n"
        "Теперь тебе доступно меню преподавателя.",
        reply_markup=teacher_menu,
    )


def register_registration_handlers(dp: Dispatcher):
    dp.message.register(start_handler, CommandStart())
    dp.message.register(register_student, F.text == "👨‍🎓 Ученик")
    dp.message.register(register_parent, F.text == "👨‍👩‍👧 Родитель")
    dp.message.register(register_teacher, F.text == "👩‍🏫 Преподаватель")