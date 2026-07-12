import asyncio

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from src.telegram_bot.handlers.registration import register_registration_handlers
from src.telegram_bot.handlers.student import register_student_handlers
from src.telegram_bot.handlers.parent import register_parent_handlers
from src.telegram_bot.handlers.teacher import register_teacher_handlers
from src.telegram_bot.handlers.demo import register_demo_handlers


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    register_registration_handlers(dp)
    register_student_handlers(dp)
    register_parent_handlers(dp)
    register_teacher_handlers(dp)
    register_demo_handlers(dp)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())