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
        [KeyboardButton(text="🔗 Привязать ребёнка")],
        [KeyboardButton(text="📷 Сдать работу ребёнка")],
        [KeyboardButton(text="📊 Прогресс ребёнка")],
        [KeyboardButton(text="📄 Отчёт за неделю")],
        [KeyboardButton(text="💬 Написать преподавателю")],
    ],
    resize_keyboard=True,
)


teacher_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🧪 Тестовая семья")],
        [KeyboardButton(text="🧪 Сдать тестовую работу")],
        [KeyboardButton(text="👨‍🎓 Ученики")],
        [KeyboardButton(text="🔗 Код для родителя")],
        [KeyboardButton(text="📚 Выдать ДЗ")],
        [KeyboardButton(text="📸 Проверки ИИ")],
        [KeyboardButton(text="📊 Сводка недели")],
        [KeyboardButton(text="📊 Статус домашнего задания")]
    ],
    resize_keyboard=True,
)
