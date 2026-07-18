from io import BytesIO
from uuid import uuid4

from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import ADMIN_TELEGRAM_ID
from src.core.roles import ROLE_PARENT
from src.repositories.user_repository import UserRepository
from src.services.parent_report_service import generate_parent_report
from src.services.photo_quality_service import assess_homework_photo
from src.telegram_bot.states.student_states import ParentSubmissionStates


MAX_PARENT_PHOTO_BYTES = 5 * 1024 * 1024


async def parent_start_submission(message: Message, state: FSMContext):
    user = UserRepository.get_by_telegram_id(message.from_user.id)
    if not user or user.get("role") != ROLE_PARENT:
        await message.answer("⛔ Загрузка доступна только родителю.")
        return
    if not ADMIN_TELEGRAM_ID:
        await message.answer("🔴 Приём работ временно недоступен.")
        return

    await state.set_state(ParentSubmissionStates.waiting_homework_photo)
    await message.answer(
        "📷 Сфотографируйте выполненную работу ребёнка.\n\n"
        "Положите лист на ровную поверхность, обеспечьте хорошее "
        "освещение и отправьте фотографию с видимыми краями листа.\n\n"
        "Отправляя фото, вы подтверждаете, что являетесь "
        "совершеннолетним родителем или законным представителем."
    )


async def parent_receive_homework_photo(
    message: Message,
    state: FSMContext,
):
    photo = message.photo[-1]
    if photo.file_size and photo.file_size > MAX_PARENT_PHOTO_BYTES:
        await message.answer(
            "⛔ Фото больше 5 Мбайт. Отправьте снимок меньшего размера."
        )
        return

    buffer = BytesIO()
    try:
        await message.bot.download(photo, destination=buffer)
        image_bytes = buffer.getvalue()
    finally:
        buffer.close()

    try:
        quality = assess_homework_photo(image_bytes)
    except ValueError:
        await message.answer(
            "🔴 Не удалось прочитать изображение. Сделайте новое фото."
        )
        return

    if not quality.acceptable:
        issues = "\n".join(f"• {issue}" for issue in quality.issues)
        await message.answer(
            "📷 Фото нужно переснять:\n\n"
            f"{issues}\n\n"
            "После пересъёмки отправьте новое фото сюда."
        )
        return

    submission_id = f"sub_{uuid4().hex[:12]}"
    await message.bot.send_photo(
        chat_id=int(ADMIN_TELEGRAM_ID),
        photo=photo.file_id,
        caption=(
            "📥 Новая работа от родителя\n"
            f"Номер: {submission_id}\n"
            "Качество фото: принято\n"
            f"Размер: {quality.width}×{quality.height}\n"
            "AI-анализ пока не запускался."
        ),
    )

    await state.clear()
    await message.answer(
        "✅ Работа принята.\n"
        "Ожидайте проверки преподавателя."
    )


async def parent_report(message: Message):
    report = generate_parent_report()
    await message.answer(report)


def register_parent_handlers(dp: Dispatcher):
    dp.message.register(
        parent_start_submission,
        F.text == "📷 Сдать работу ребёнка",
    )
    dp.message.register(
        parent_receive_homework_photo,
        ParentSubmissionStates.waiting_homework_photo,
        F.photo,
    )
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
