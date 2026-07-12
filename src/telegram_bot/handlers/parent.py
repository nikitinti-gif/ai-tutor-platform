from aiogram import Dispatcher, F
from aiogram.types import Message

from src.services.parent_report_service import generate_parent_report


async def parent_report(message: Message):
    report = generate_parent_report()
    await message.answer(report)


def register_parent_handlers(dp: Dispatcher):
    dp.message.register(
        parent_report,
        F.text.in_({
            "📊 Отчёт",
            "📊 Отчет",
            "📈 Отчёт по ученику",
            "📈 Отчет по ученику",
            "👨‍👩‍👧 Отчёт по ученику",
            "👨‍👩‍👧 Отчет по ученику",
            "📋 Отчёт для родителя",
            "📋 Отчет для родителя",
            "📊 Прогресс ребёнка",
            "📊 Прогресс ребенка",
            "👨‍👩‍👧 Родительский отчёт",
            "👨‍👩‍👧 Родительский отчет",
        }),
    )