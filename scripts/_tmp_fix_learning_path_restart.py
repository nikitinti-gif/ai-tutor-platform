from pathlib import Path

student = Path('src/telegram_bot/handlers/student.py')
text = student.read_text(encoding='utf-8')
anchor = '''async def start_ege_diagnostic_pilot(message: Message, state: FSMContext):\n'''
insert = '''async def resume_ege_learning_path_after_restart(message: Message, state: FSMContext) -> None:\n    \"\"\"Recover a persisted Learning Path when Render/redeploy cleared aiogram FSM.\"\"\"\n    saved = get_ege_session(message.from_user.id)\n    if not saved or saved.get(\"status\") != \"learning_path_in_progress\":\n        from aiogram.dispatcher.event.bases import SkipHandler\n        raise SkipHandler\n\n    from src.services.ege_exam_service import ExamAttempt\n\n    attempt = ExamAttempt.from_dict(saved.get(\"attempt\"))\n    if not attempt.learning_path:\n        from aiogram.dispatcher.event.bases import SkipHandler\n        raise SkipHandler\n    await state.set_state(StudentEgeExamStates.waiting_learning_path_answer)\n    await state.update_data(ege_attempt=attempt.to_dict())\n    await receive_ege_learning_path_answer(message, state)\n\n\n'''
if 'async def resume_ege_learning_path_after_restart' not in text:
    if anchor not in text:
        raise SystemExit('student resume insertion anchor not found')
    text = text.replace(anchor, insert + anchor, 1)

old = '''    dp.message.register(student_question, F.text == \"❓ Задать вопрос\")\n    dp.message.register(resume_ege_tutor_pilot_after_restart, F.text)\n'''
new = '''    dp.message.register(student_question, F.text == \"❓ Задать вопрос\")\n    dp.message.register(resume_ege_learning_path_after_restart, F.text)\n    dp.message.register(resume_ege_tutor_pilot_after_restart, F.text)\n'''
if old not in text:
    raise SystemExit('student registration anchor not found')
text = text.replace(old, new, 1)
student.write_text(text, encoding='utf-8')

service = Path('src/services/ege_learning_path.py')
text = service.read_text(encoding='utf-8')
old = '''        \"support\": \"При переводе дели число на основание и читай остатки снизу вверх.\",\n        \"prompt\": \"Переведи 47 из десятичной системы в 16-ричную. Запиши только результат.\",\n'''
new = '''        \"support\": \"При переводе дели число на основание и читай остатки снизу вверх.\",\n        \"worked_example\": \"Похожий пример: 45 = 2·16 + 13. Остаток 13 — это D, поэтому 45₁₀ = 2D₁₆. Теперь тем же способом разложи 47.\",\n        \"prompt\": \"Переведи 47 из десятичной системы в 16-ричную. Запиши только результат.\",\n'''
if old not in text:
    raise SystemExit('small conversion block not found')
text = text.replace(old, new, 1)
old = '''    support = \"\"\n    if path.attempts_on_step == 0:\n        support = f\"\\n\\n💡 Перед задачей:\\n{step['support']}\"\n    else:\n        support = f\"\\n\\n💡 Подсказка:\\n{step['support']}\"\n'''
new = '''    support = \"\"\n    if path.attempts_on_step == 0:\n        support = f\"\\n\\n💡 Перед задачей:\\n{step['support']}\"\n    elif path.attempts_on_step >= 2 and step.get(\"worked_example\"):\n        support = (\n            f\"\\n\\n🧑‍🏫 Разберём похожий пример:\\n{step['worked_example']}\"\n            f\"\\n\\n💡 Теперь вернись к своей задаче:\\n{step['support']}\"\n        )\n    else:\n        support = f\"\\n\\n💡 Подсказка:\\n{step['support']}\"\n'''
if old not in text:
    raise SystemExit('render support block not found')
text = text.replace(old, new, 1)
service.write_text(text, encoding='utf-8')

test = Path('tests/test_ege_learning_path.py')
t = test.read_text(encoding='utf-8')
addition = '''\n\ndef test_repeated_foundation_error_escalates_to_worked_example():\n    path = build_learning_path(14)\n    submit_answer(path, TASK14_LEVELS[0][\"answers\"][0])\n    submit_answer(path, \"D2\")\n    submit_answer(path, \"F2\")\n    text = render_current_step(path)\n    assert \"Разберём похожий пример\" in text\n    assert \"45 = 2·16 + 13\" in text\n    assert \"2D\" in text\n    assert \"47\" in text\n'''
if 'test_repeated_foundation_error_escalates_to_worked_example' not in t:
    t += addition
test.write_text(t, encoding='utf-8')

test = Path('tests/test_student_diagnostic_handler_flow.py')
t = test.read_text(encoding='utf-8')
addition = '''\n\ndef test_learning_path_answer_survives_restart(monkeypatch):\n    from src.services.ege_exam_service import ExamAttempt\n    from src.services.ege_learning_path import TASK14_LEVELS, build_learning_path, submit_answer\n\n    sessions = {}\n    _patch_sessions(monkeypatch, sessions)\n    attempt = ExamAttempt()\n    attempt.results[14] = False\n    path = build_learning_path(14)\n    for level in TASK14_LEVELS[:5]:\n        result = submit_answer(path, str(level[\"answers\"][0]))\n        assert result[\"is_correct\"] is True\n    assert path.current_index == 5\n    attempt.learning_path = path.to_dict()\n    sessions[42] = {\"attempt\": attempt.to_dict(), \"status\": \"learning_path_in_progress\"}\n\n    # Simulate a Render restart: aiogram FSM is empty, but persisted session survives.\n    state = FakeState()\n    message = FakeMessage(text=str(TASK14_LEVELS[5][\"answers\"][0]))\n    asyncio.run(student_handler.resume_ege_learning_path_after_restart(message, state))\n\n    restored = sessions[42][\"attempt\"][\"learning_path\"]\n    assert restored[\"current_index\"] == 6\n    assert any(\"Поднимаемся на следующий уровень\" in item for item in message.answers)\n    assert any(\"ШАГ 7/7\" in item for item in message.answers)\n'''
if 'test_learning_path_answer_survives_restart' not in t:
    t += addition
test.write_text(t, encoding='utf-8')
