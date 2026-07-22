import asyncio
import logging
from io import BytesIO
from uuid import uuid4

from aiogram import Dispatcher, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ADMIN_TELEGRAM_ID
from src.core.roles import ROLE_PARENT
from src.repositories.family_link_repository import FamilyLinkRepository
from src.repositories.adaptive_task_repository import AdaptiveTaskRepository
from src.repositories.user_repository import UserRepository
from src.repositories.submission_repository import SubmissionRepository
from src.services.parent_report_service import generate_parent_report
from src.services.family_link_service import (
    hash_link_code,
    is_synthetic_student_id,
)
from src.services.photo_quality_service import assess_homework_photo
from src.telegram_bot.states.student_states import (
    ParentFamilyLinkStates,
    ParentSubmissionStates,
)


MAX_PARENT_PHOTO_BYTES = 5 * 1024 * 1024
logger = logging.getLogger(__name__)


def is_admin(message: Message) -> bool:
    return bool(
        message.from_user
        and ADMIN_TELEGRAM_ID
        and str(message.from_user.id) == str(ADMIN_TELEGRAM_ID)
    )


async def parent_start_family_link(message: Message, state: FSMContext):
    parent = UserRepository.get_by_telegram_id(message.from_user.id)
    if not parent or parent.get("role") != ROLE_PARENT:
        await message.answer("⛔ Привязка доступна только родителю.")
        return

    await state.set_state(ParentFamilyLinkStates.waiting_link_code)
    await message.answer(
        "🔗 Введите одноразовый код, полученный от преподавателя."
    )


async def parent_receive_family_link_code(
    message: Message,
    state: FSMContext,
):
    try:
        code_hash = hash_link_code(message.text)
    except (TypeError, ValueError):
        await message.answer(
            "Код должен состоять из 8 символов. Проверьте и отправьте снова."
        )
        return

    try:
        student_id = await asyncio.to_thread(
            FamilyLinkRepository.consume_code,
            code_hash,
            message.from_user.id,
        )
    except Exception:
        logger.exception("Parent link code could not be consumed")
        await message.answer(
            "🔴 Не удалось проверить код. Попробуйте через несколько минут."
        )
        return

    if student_id is None:
        await message.answer(
            "⛔ Код недействителен, уже использован или истёк. "
            "Запросите новый код у преподавателя."
        )
        return

    await state.clear()
    await message.answer(
        "✅ Ребёнок привязан. Теперь можно отправлять выполненные работы."
    )


async def parent_start_submission(message: Message, state: FSMContext):
    user = UserRepository.get_by_telegram_id(message.from_user.id)
    if (not user or user.get("role") != ROLE_PARENT) and not is_admin(message):
        await message.answer("⛔ Загрузка доступна только родителю.")
        return
    if not ADMIN_TELEGRAM_ID:
        await message.answer("🔴 Приём работ временно недоступен.")
        return

    try:
        student_id = await asyncio.to_thread(
            FamilyLinkRepository.get_student_id,
            message.from_user.id,
        )
    except Exception:
        logger.exception("Parent link could not be loaded")
        await message.answer("🔴 Приём работ временно недоступен.")
        return
    if student_id is None:
        await message.answer(
            "🔗 Сначала привяжите ребёнка одноразовым кодом преподавателя."
        )
        return

    await state.set_state(ParentSubmissionStates.waiting_homework_photo)
    await state.update_data(student_telegram_id=student_id)
    await message.answer(
        "📷 Сфотографируйте выполненную работу ребёнка.\n\n"
        "Положите лист на ровную поверхность, обеспечьте хорошее "
        "освещение и отправьте фотографию с видимыми краями листа.\n\n"
        "Отправляя фото, вы подтверждаете, что являетесь "
        "совершеннолетним родителем или законным представителем."
    )


async def parent_start_adaptive_submission(
    callback: CallbackQuery,
    state: FSMContext,
):
    task_set_id = callback.data.split(":", maxsplit=1)[1]
    user = UserRepository.get_by_telegram_id(callback.from_user.id)
    if (not user or user.get("role") != ROLE_PARENT) and not is_admin(callback):
        await callback.answer("Загрузка доступна только семье.", show_alert=True)
        return

    try:
        task_set = await asyncio.to_thread(
            AdaptiveTaskRepository.get, task_set_id
        )
    except Exception:
        logger.exception("Adaptive task set could not be loaded: %s", task_set_id)
        await callback.answer("Набор временно недоступен.", show_alert=True)
        return

    if not task_set or task_set.get("parent_id") != callback.from_user.id:
        await callback.answer("Этот набор недоступен вашему аккаунту.", show_alert=True)
        return
    if task_set.get("status") != "sent":
        message = (
            "Решение по этому набору уже отправлено."
            if task_set.get("status") == "submitted"
            else "Набор пока нельзя сдавать."
        )
        await callback.answer(message, show_alert=True)
        return

    await state.set_state(ParentSubmissionStates.waiting_homework_photo)
    await state.update_data(
        student_telegram_id=task_set["student_id"],
        task_set_id=task_set_id,
    )
    await callback.answer()
    await callback.message.answer(
        f"📷 Отправьте одно фото решения по набору {task_set_id}.\n\n"
        "На снимке должны быть видны ответы на лёгкое, среднее и сложное "
        "задания. Подпишите уровни 1, 2 и 3."
    )


async def parent_receive_homework_photo(
    message: Message,
    state: FSMContext,
):
    state_data = await state.get_data()
    student_id = state_data.get("student_telegram_id")
    task_set_id = state_data.get("task_set_id")
    if not isinstance(student_id, int):
        await state.clear()
        await message.answer(
            "🔗 Связь с ребёнком не найдена. Выполните привязку снова."
        )
        return

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
    submission = {
        "submission_id": submission_id,
        "parent_telegram_id": message.from_user.id,
        "student_telegram_id": student_id,
        "is_synthetic": is_synthetic_student_id(student_id),
        "telegram_file_id": photo.file_id,
        "telegram_file_unique_id": photo.file_unique_id,
        "status": "accepted",
        "photo_width": quality.width,
        "photo_height": quality.height,
        "quality_metrics": {
            "brightness": round(quality.brightness, 2),
            "contrast": round(quality.contrast, 2),
            "sharpness": round(quality.sharpness, 2),
        },
        "task_set_id": task_set_id,
    }
    try:
        await asyncio.to_thread(SubmissionRepository.create, submission)
    except Exception:
        logger.exception("Parent submission was not saved: %s", submission_id)
        await message.answer(
            "🔴 Не удалось сохранить работу. Попробуйте отправить фото "
            "ещё раз через несколько минут."
        )
        return

    try:
        await message.bot.send_photo(
            chat_id=int(ADMIN_TELEGRAM_ID),
            photo=photo.file_id,
            caption=(
                "📥 Новая работа от родителя\n"
                f"Номер: {submission_id}\n"
                f"Диагностический набор: {task_set_id or 'не указан'}\n"
                "Качество фото: принято\n"
                f"Размер: {quality.width}×{quality.height}\n"
                "Очередь: PostgreSQL\n"
                "Данные: "
                f"{'синтетические' if is_synthetic_student_id(student_id) else 'пилотные'}\n"
                "AI-анализ пока не запускался."
            ),
        )
    except Exception:
        logger.exception(
            "Teacher was not notified about submission: %s",
            submission_id,
        )
    else:
        try:
            await asyncio.to_thread(
                SubmissionRepository.mark_teacher_notified,
                submission_id,
            )
        except Exception:
            logger.exception(
                "Teacher notification was not marked: %s",
                submission_id,
            )

    await state.clear()
    diagnostic_line = (
        f"Диагностический набор: {task_set_id}\n" if task_set_id else ""
    )
    await message.answer(
        "✅ Работа принята.\n"
        f"{diagnostic_line}"
        "Ожидайте проверки преподавателя."
    )


async def parent_report(message: Message):
    report = generate_parent_report()
    await message.answer(report)


def register_parent_handlers(dp: Dispatcher):
    dp.callback_query.register(
        parent_start_adaptive_submission,
        F.data.startswith("submit_adaptive:"),
    )
    dp.message.register(
        parent_start_family_link,
        F.text == "🔗 Привязать ребёнка",
    )
    dp.message.register(
        parent_receive_family_link_code,
        ParentFamilyLinkStates.waiting_link_code,
        F.text,
    )
    dp.message.register(
        parent_start_submission,
        F.text.in_({
            "📷 Сдать работу ребёнка",
            "🧪 Сдать тестовую работу",
        }),
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
