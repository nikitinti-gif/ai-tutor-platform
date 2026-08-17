from pathlib import Path

# Persist learning-path state inside ExamAttempt so deploy/restart cannot lose it.
p = Path('src/services/ege_exam_service.py')
text = p.read_text(encoding='utf-8')
old = '    tutor_pilot_stage: str = "supported"\n'
new = '    tutor_pilot_stage: str = "supported"\n    learning_path: dict = field(default_factory=dict)\n'
if old not in text:
    raise SystemExit('ExamAttempt field anchor not found')
text = text.replace(old, new, 1)
old = '''            int(data.get("tutor_pilot_index", 0)),\n            str(data.get("tutor_pilot_stage", "supported")),\n        )\n'''
new = '''            int(data.get("tutor_pilot_index", 0)),\n            str(data.get("tutor_pilot_stage", "supported")),\n            dict(data.get("learning_path", {})),\n        )\n'''
if old not in text:
    raise SystemExit('ExamAttempt from_dict anchor not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# Add a dedicated state; do not overload old remediation/probe FSM.
p = Path('src/telegram_bot/states/student_states.py')
text = p.read_text(encoding='utf-8')
old = '    waiting_remediation_answer = State()\n'
new = '    waiting_remediation_answer = State()\n    waiting_learning_path_answer = State()\n'
if old not in text:
    raise SystemExit('student state anchor not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# Integrate the first real Learning Path into the full /ege2026 flow.
p = Path('src/telegram_bot/handlers/student.py')
text = p.read_text(encoding='utf-8')
anchor = '\n\nasync def receive_ege_answer(message: Message, state: FSMContext):\n'
if anchor not in text:
    raise SystemExit('receive_ege_answer anchor not found')
block = r'''

async def _start_learning_path_after_exam_if_available(message: Message, state: FSMContext, attempt) -> bool:
    """Start the first progressive post-exam branch for an actually failed task."""
    if attempt.results.get(14) is not False:
        return False
    from src.services.ege_learning_path import build_learning_path, render_current_step

    path = build_learning_path(14, source="diagnostic_exam")
    attempt.learning_path = path.to_dict()
    save_ege_session(message.from_user.id, attempt.to_dict(), status="learning_path_in_progress")
    await state.set_state(StudentEgeExamStates.waiting_learning_path_answer)
    await state.update_data(ege_attempt=attempt.to_dict())
    await message.answer(
        "🧭 В пробном КЕГЭ задание №14 не решено. Теперь не будем искать ошибку случайными вопросами.\n\n"
        "Построил учебную ветку от самых базовых навыков до настоящей формулировки №14. "
        "Каждый следующий шаг открывается только после правильного ответа на предыдущем."
    )
    await message.answer(render_current_step(path))
    return True


async def receive_ege_learning_path_answer(message: Message, state: FSMContext) -> None:
    """Advance one deterministic reasoning Learning Path step."""
    from src.services.ege_exam_service import ExamAttempt
    from src.services.ege_learning_path import LearningPath, render_current_step, submit_answer

    data = await state.get_data()
    attempt_data = data.get("ege_attempt")
    if not attempt_data:
        saved = get_ege_session(message.from_user.id)
        attempt_data = saved.get("attempt") if saved else None
    if not attempt_data:
        await state.clear()
        await message.answer("Учебная ветка не найдена. Запусти /ege2026.")
        return

    attempt = ExamAttempt.from_dict(attempt_data)
    if not attempt.learning_path:
        await state.clear()
        await message.answer("Учебная ветка №14 не найдена.")
        return

    path = LearningPath.from_dict(attempt.learning_path)
    result = submit_answer(path, message.text or "")
    attempt.learning_path = path.to_dict()
    await state.update_data(ege_attempt=attempt.to_dict())

    if result["status"] == "mastered":
        save_ege_session(message.from_user.id, attempt.to_dict(), status="completed")
        await state.clear()
        await message.answer(
            "🏆 Ветка №14 пройдена полностью: база → промежуточные задачи → аналог → "
            "настоящий экзаменационный уровень. Навык подтверждён новой задачей, а не одной подсказкой."
        )
        return

    save_ege_session(message.from_user.id, attempt.to_dict(), status="learning_path_in_progress")
    if result["is_correct"]:
        await message.answer("✅ Верно. Поднимаемся на следующий уровень.")
    elif result.get("needs_teaching"):
        await message.answer(
            "Пока этот шаг не закрепился. Не повышаю сложность: сначала разберём базовое правило ещё раз."
        )
    else:
        await message.answer("Пока неверно. Остаёмся на этом уровне и разберём его без спешки.")
    await message.answer(render_current_step(path))
'''
text = text.replace(anchor, block + anchor, 1)

# Full exam completion now chooses the learning branch before legacy micro-probes.
old = '''    if attempt.finished:\n        await message.answer(f"{result.message}\\n\\n{render_summary(attempt)}")\n        await _begin_ege_diagnostics(message, state, attempt)\n        return\n'''
new = '''    if attempt.finished:\n        await message.answer(f"{result.message}\\n\\n{render_summary(attempt)}")\n        if await _start_learning_path_after_exam_if_available(message, state, attempt):\n            return\n        await _begin_ege_diagnostics(message, state, attempt)\n        return\n'''
if old not in text:
    raise SystemExit('receive_ege_answer finish block not found')
text = text.replace(old, new, 1)

old = '''    attempt = ExamAttempt.from_dict(attempt_data)\n    await message.answer(render_summary(attempt))\n    await _begin_ege_diagnostics(message, state, attempt)\n'''
new = '''    attempt = ExamAttempt.from_dict(attempt_data)\n    await message.answer(render_summary(attempt))\n    if await _start_learning_path_after_exam_if_available(message, state, attempt):\n        return\n    await _begin_ege_diagnostics(message, state, attempt)\n'''
if old not in text:
    raise SystemExit('finish_ege_exam block not found')
text = text.replace(old, new, 1)

# Resume a Learning Path after Render restart.
old = '''    saved = get_ege_session(message.from_user.id)\n    if saved and saved.get("status") == "remediation_in_progress":\n'''
new = '''    saved = get_ege_session(message.from_user.id)\n    if saved and saved.get("status") == "learning_path_in_progress":\n        from src.services.ege_exam_service import ExamAttempt\n        from src.services.ege_learning_path import LearningPath, render_current_step\n\n        attempt = ExamAttempt.from_dict(saved.get("attempt"))\n        path = LearningPath.from_dict(attempt.learning_path)\n        await state.set_state(StudentEgeExamStates.waiting_learning_path_answer)\n        await state.update_data(ege_attempt=attempt.to_dict())\n        await message.answer("▶️ Продолжаем индивидуальную учебную ветку №14.")\n        await message.answer(render_current_step(path))\n        return\n    if saved and saved.get("status") == "remediation_in_progress":\n'''
if old not in text:
    raise SystemExit('start_ege_exam resume anchor not found')
text = text.replace(old, new, 1)

# Register new state handler before generic student handlers.
old = '''    dp.message.register(\n        receive_ege_remediation_answer,\n        StudentEgeExamStates.waiting_remediation_answer,\n        F.text,\n    )\n'''
new = old + '''    dp.message.register(\n        receive_ege_learning_path_answer,\n        StudentEgeExamStates.waiting_learning_path_answer,\n        F.text,\n    )\n'''
if old not in text:
    raise SystemExit('handler registration anchor not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# Add integration-level regression around ExamAttempt persistence.
p = Path('tests/test_ege_learning_path.py')
text = p.read_text(encoding='utf-8')
addition = r'''


def test_exam_attempt_persists_learning_path_state():
    from src.services.ege_exam_service import ExamAttempt
    path = build_learning_path(14)
    submit_answer(path, TASK14_LEVELS[0]["answers"][0])
    attempt = ExamAttempt()
    attempt.results[14] = False
    attempt.learning_path = path.to_dict()
    restored = ExamAttempt.from_dict(attempt.to_dict())
    restored_path = LearningPath.from_dict(restored.learning_path)
    assert restored.results[14] is False
    assert restored_path.current_index == 1
    assert current_step(restored_path)["id"] == "small_conversion"
'''
if 'test_exam_attempt_persists_learning_path_state' not in text:
    text += addition
p.write_text(text, encoding='utf-8')
