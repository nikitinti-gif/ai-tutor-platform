from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

from src.services.demo_data_service import create_informatics_demo


async def demo_informatics(message: Message):
    result = create_informatics_demo(
        user_id=message.from_user.id,
        full_name=message.from_user.full_name,
    )

    await message.answer(result)


def register_demo_handlers(dp: Dispatcher):
    dp.message.register(demo_informatics, Command("demo_informatics"))