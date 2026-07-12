from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


student_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📚 Моё ДЗ")],
        [KeyboardButton(text="📸 Проверить решение")],
        [KeyboardButton(text="📊 Мой прогресс")],
        [KeyboardButton(text="❓ Задать вопрос")],
    ],
    resize_keyboard=True,
)


parent_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 Прогресс ребёнка")],
        [KeyboardButton(text="📄 Отчёт за неделю")],
        [KeyboardButton(text="💬 Написать преподавателю")],
    ],
    resize_keyboard=True,
)


teacher_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👨‍🎓 Ученики")],
        [KeyboardButton(text="📚 Выдать ДЗ")],
        [KeyboardButton(text="📸 Проверки ИИ")],
        [KeyboardButton(text="📊 Сводка недели")],
        [KeyboardButton(text="📊 Статус домашнего задания")]
    ],
    resize_keyboard=True,
)