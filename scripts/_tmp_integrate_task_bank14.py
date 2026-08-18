from pathlib import Path

# 1) Persist curated-bank progress inside ExamAttempt.
p = Path('src/services/ege_exam_service.py')
text = p.read_text(encoding='utf-8')
old = '    learning_path: dict = field(default_factory=dict)\n'
new = old + '    task_bank: dict = field(default_factory=dict)\n'
if 'task_bank: dict = field(default_factory=dict)' not in text:
    text = text.replace(old, new, 1)
old_ctor = '''            str(data.get("tutor_pilot_stage", "supported")),\n            dict(data.get("learning_path", {})),\n        )\n'''
new_ctor = '''            str(data.get("tutor_pilot_stage", "supported")),\n            dict(data.get("learning_path", {})),\n            dict(data.get("task_bank", {})),\n        )\n'''
if old_ctor in text:
    text = text.replace(old_ctor, new_ctor, 1)
p.write_text(text, encoding='utf-8')

# 2) Turn the one-shot task bank into a persisted two-task practice stage and
#    automatically start it after the progressive №14 path.
p = Path('src/telegram_bot/handlers/student.py')
text = p.read_text(encoding='utf-8')
start = text.index('async def start_task14_bank_pilot')
end = text.index('\n\nasync def start_ege_diagnostic_pilot', start)
replacement = r'''async def _start_task14_bank_practice(message: Message, state: FSMContext, attempt, *, pilot: bool = False) -> None:
    """Start/continue curated real-task practice after the deterministic learning path."""
    from src.services.ege_task_bank import get_task, render_task

    sequence = ["reshuege-92256", "reshuege-92258"]
    attempt.task_bank = {
        "task_number": 14,
        "sequence": sequence,
        "current_index": 0,
        "correct_ids": [],
        "attempts": {},
        "source": "admin_pilot" if pilot else "post_learning_path",
    }
    task = get_task(sequence[0])
    save_ege_session(message.from_user.id, attempt.to_dict(), status="task_bank_in_progress")
    await state.set_state(StudentEgeExamStates.waiting_task_bank_answer)
    await state.update_data(ege_attempt=attempt.to_dict())
    if pilot:
        await message.answer(
            "🧪 Проверяем связный Task Bank №14: теперь после правильного ответа Tutor не останавливается, "
            "а даёт следующую реальную вариацию."
        )
    else:
        await message.answer(
            "✅ Учебная лестница пройдена. Теперь проверим перенос на реальных задачах №14 из курируемого банка. "
            "Нужно решить две разные вариации без подсказок."
        )
    await message.answer(render_task(task))


async def start_task14_bank_pilot(message: Message, state: FSMContext) -> None:
    """Admin shortcut for the persisted multi-task curated bank stage."""
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
    await _start_task14_bank_practice(message, state, attempt, pilot=True)


async def receive_task14_bank_answer(message: Message, state: FSMContext) -> None:
    from src.services.ege_exam_service import ExamAttempt
    from src.services.ege_task_bank import get_task, render_task, validate_answer

    data = await state.get_data()
    attempt_data = data.get("ege_attempt")
    if not attempt_data:
        saved = get_ege_session(message.from_user.id)
        attempt_data = saved.get("attempt") if saved else None
    if not attempt_data:
        await state.clear()
        await message.answer("Практика Task Bank не найдена. Запусти /test_task_bank14.")
        return

    attempt = ExamAttempt.from_dict(attempt_data)
    bank = dict(attempt.task_bank or {})
    sequence = list(bank.get("sequence") or [])
    index = int(bank.get("current_index", 0))
    if not sequence or index >= len(sequence):
        await state.clear()
        await message.answer("Практика Task Bank уже завершена.")
        return

    task = get_task(sequence[index])
    answer = message.text or ""
    attempts = dict(bank.get("attempts") or {})
    attempts[task.task_id] = int(attempts.get(task.task_id, 0)) + 1
    bank["attempts"] = attempts

    if not validate_answer(task.task_id, answer):
        attempt.task_bank = bank
        save_ege_session(message.from_user.id, attempt.to_dict(), status="task_bank_in_progress")
        await state.update_data(ege_attempt=attempt.to_dict())
        await message.answer(
            "❌ Пока неверно. Это не отменяет уже освоенные базовые навыки: перед нами другая вариация №14. "
            "Остаёмся на этой задаче. Попробуй ещё раз; ответ по-прежнему проверяет локальный Python."
        )
        return

    correct_ids = list(bank.get("correct_ids") or [])
    if task.task_id not in correct_ids:
        correct_ids.append(task.task_id)
    bank["correct_ids"] = correct_ids
    bank["current_index"] = index + 1
    attempt.task_bank = bank

    if bank["current_index"] < len(sequence):
        next_task = get_task(sequence[bank["current_index"]])
        save_ege_session(message.from_user.id, attempt.to_dict(), status="task_bank_in_progress")
        await state.update_data(ege_attempt=attempt.to_dict())
        await message.answer(
            "✅ Верно. Python подтвердил ответ. Теперь новая вариация №14 — проверяем, переносится ли навык, "
            "а не запомнен ли один шаблон."
        )
        await message.answer(render_task(next_task))
        return

    save_ege_session(message.from_user.id, attempt.to_dict(), status="completed")
    await state.clear()
    await message.answer(
        "🏆 Практика №14 завершена: учебная ветка → экзаменационный уровень → две разные реальные задачи банка. "
        "Обе проверены локальным Python. Теперь результат можно считать сильным подтверждением переноса навыка."
    )


async def resume_task14_bank_after_restart(message: Message, state: FSMContext) -> None:
    """Recover curated bank practice after Render/redeploy cleared aiogram FSM."""
    saved = get_ege_session(message.from_user.id)
    if not saved or saved.get("status") != "task_bank_in_progress":
        from aiogram.dispatcher.event.bases import SkipHandler
        raise SkipHandler
    from src.services.ege_exam_service import ExamAttempt

    attempt = ExamAttempt.from_dict(saved.get("attempt"))
    if not attempt.task_bank:
        from aiogram.dispatcher.event.bases import SkipHandler
        raise SkipHandler
    await state.set_state(StudentEgeExamStates.waiting_task_bank_answer)
    await state.update_data(ege_attempt=attempt.to_dict())
    await receive_task14_bank_answer(message, state)
'''
text = text[:start] + replacement + text[end:]

old_mastered = '''    if result["status"] == "mastered":\n        save_ege_session(message.from_user.id, attempt.to_dict(), status="completed")\n        await state.clear()\n        await message.answer(\n            "🏆 Ветка №14 пройдена полностью: база → промежуточные задачи → аналог → "\n            "настоящий экзаменационный уровень. Навык подтверждён новой задачей, а не одной подсказкой."\n        )\n        return\n'''
new_mastered = '''    if result["status"] == "mastered":\n        await message.answer(\n            "🏆 Учебная ветка №14 пройдена до независимого экзаменационного переноса."\n        )\n        await _start_task14_bank_practice(message, state, attempt)\n        return\n'''
if old_mastered not in text:
    raise SystemExit('mastered block not found')
text = text.replace(old_mastered, new_mastered, 1)

# Register restart recovery as the final text fallback, alongside existing recovery handlers.
anchor = '    dp.message.register(resume_ege_learning_path_after_restart, F.text)\n'
if anchor in text and 'dp.message.register(resume_task14_bank_after_restart, F.text)' not in text:
    text = text.replace(anchor, anchor + '    dp.message.register(resume_task14_bank_after_restart, F.text)\n', 1)
elif 'dp.message.register(resume_task14_bank_after_restart, F.text)' not in text:
    # Fallback: insert before register function ends after existing recovery registration.
    marker = '    dp.message.register(resume_ege_tutor_pilot_after_restart, F.text)\n'
    if marker in text:
        text = text.replace(marker, marker + '    dp.message.register(resume_task14_bank_after_restart, F.text)\n', 1)
    else:
        raise SystemExit('restart registration anchor not found')

p.write_text(text, encoding='utf-8')

# 3) Regression tests: correct bank answer must advance, second correct must complete;
#    the persisted stage must survive a restart.
t = Path('tests/test_student_diagnostic_handler_flow.py')
txt = t.read_text(encoding='utf-8')
old_test_start = txt.find('def test_admin_can_issue_curated_task_bank14_item')
if old_test_start != -1:
    txt = txt[:old_test_start].rstrip() + '\n'

txt += r'''

def test_task_bank14_advances_instead_of_stopping(monkeypatch):
    from src.services.ege_task_bank import get_task

    sessions = {}
    _patch_sessions(monkeypatch, sessions)
    state = FakeState()
    start = FakeMessage(user_id=42)
    asyncio.run(student_handler.start_task14_bank_pilot(start, state))

    assert state.data["ege_attempt"]["task_bank"]["current_index"] == 0
    first = get_task("reshuege-92256")
    answer1 = FakeMessage(user_id=42, text=first.canonical_answer)
    asyncio.run(student_handler.receive_task14_bank_answer(answer1, state))
    assert any("новая вариация №14" in item for item in answer1.answers)
    assert any("№92258" in item for item in answer1.answers)
    assert state.data["ege_attempt"]["task_bank"]["current_index"] == 1

    second = get_task("reshuege-92258")
    answer2 = FakeMessage(user_id=42, text=second.canonical_answer)
    asyncio.run(student_handler.receive_task14_bank_answer(answer2, state))
    assert any("Практика №14 завершена" in item for item in answer2.answers)
    assert sessions[42]["status"] == "completed"


def test_task_bank14_answer_survives_restart(monkeypatch):
    from src.services.ege_exam_service import ExamAttempt
    from src.services.ege_task_bank import get_task

    sessions = {}
    _patch_sessions(monkeypatch, sessions)
    attempt = ExamAttempt()
    attempt.task_bank = {
        "task_number": 14,
        "sequence": ["reshuege-92256", "reshuege-92258"],
        "current_index": 0,
        "correct_ids": [],
        "attempts": {},
        "source": "post_learning_path",
    }
    sessions[42] = {"attempt": attempt.to_dict(), "status": "task_bank_in_progress"}
    state = FakeState()
    first = get_task("reshuege-92256")
    message = FakeMessage(user_id=42, text=first.canonical_answer)
    asyncio.run(student_handler.resume_task14_bank_after_restart(message, state))
    assert any("№92258" in item for item in message.answers)
    assert sessions[42]["attempt"]["task_bank"]["current_index"] == 1
'''
t.write_text(txt, encoding='utf-8')
