from pathlib import Path

p = Path('src/telegram_bot/handlers/student.py')
text = p.read_text(encoding='utf-8')
anchor = '\n\nasync def _start_learning_path_after_exam_if_available(message: Message, state: FSMContext, attempt) -> bool:\n'
if anchor not in text:
    raise SystemExit('learning path helper anchor not found')
block = r'''

async def start_task14_learning_path_pilot(message: Message, state: FSMContext) -> None:
    """Admin-only shortcut to test the post-exam task14 branch without 27 tasks."""
    is_admin = bool(
        ADMIN_TELEGRAM_ID
        and str(message.from_user.id) == str(ADMIN_TELEGRAM_ID)
    )
    if not is_admin:
        await message.answer("⛔ Эта тестовая команда доступна только администратору.")
        return
    from src.services.ege_exam_service import ExamAttempt

    delete_ege_session(message.from_user.id)
    await state.clear()
    attempt = ExamAttempt()
    attempt.results[14] = False
    await message.answer(
        "🧪 Симуляция результата пробного КЕГЭ: №14 не решено. "
        "Проверяем новую модель обучения от базы до экзамена."
    )
    await _start_learning_path_after_exam_if_available(message, state, attempt)
'''
text = text.replace(anchor, block + anchor, 1)
old = '    dp.message.register(start_ege_tutor_pilot, F.text == "/test_ege_tutor")\n'
new = old + '    dp.message.register(start_task14_learning_path_pilot, F.text == "/test_learning_path14")\n'
if old not in text:
    raise SystemExit('register pilot anchor not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')
