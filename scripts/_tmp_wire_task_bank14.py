from pathlib import Path

states = Path('src/telegram_bot/states/student_states.py')
text = states.read_text(encoding='utf-8')
needle = '    waiting_learning_path_answer = State()\n'
if 'waiting_task_bank_answer' not in text:
    text = text.replace(needle, needle + '    waiting_task_bank_answer = State()\n')
states.write_text(text, encoding='utf-8')

p = Path('src/telegram_bot/handlers/student.py')
text = p.read_text(encoding='utf-8')
anchor = '\n\nasync def start_ege_diagnostic_pilot(message: Message, state: FSMContext):\n'
block = '''\n\nasync def start_task14_bank_pilot(message: Message, state: FSMContext) -> None:\n    \"\"\"Admin shortcut: issue one curated real-world task14 bank item.\"\"\"\n    is_admin = bool(\n        ADMIN_TELEGRAM_ID\n        and str(message.from_user.id) == str(ADMIN_TELEGRAM_ID)\n    )\n    if not is_admin:\n        await message.answer(\"⛔ Эта тестовая команда доступна только администратору.\")\n        return\n    from src.services.ege_task_bank import get_task, render_task\n\n    await state.clear()\n    task = get_task(\"reshuege-92256\")\n    await state.set_state(StudentEgeExamStates.waiting_task_bank_answer)\n    await state.update_data(task_bank_id=task.task_id)\n    await message.answer(\n        \"🧪 Проверяем Task Bank: реальная задача №14 из курируемого внешнего банка, \"\n        \"но эталон вычисляет наш Python.\"\n    )\n    await message.answer(render_task(task))\n\n\nasync def receive_task14_bank_answer(message: Message, state: FSMContext) -> None:\n    from src.services.ege_task_bank import get_task, validate_answer\n\n    data = await state.get_data()\n    task_id = data.get(\"task_bank_id\")\n    if not task_id:\n        await state.clear()\n        await message.answer(\"Задача банка не найдена. Запусти /test_task_bank14.\")\n        return\n    task = get_task(str(task_id))\n    is_correct = validate_answer(task.task_id, message.text or \"\")\n    await state.clear()\n    if is_correct:\n        await message.answer(\n            \"✅ Верно. Это была задача из внешнего курируемого банка, \"\n            \"а правильность ответа определил локальный Python-валидатор.\"\n        )\n    else:\n        await message.answer(\n            \"❌ Пока неверно. Ответ не сверялся с сайтом: его независимо вычислил Python Tutor. \"\n            \"Позже эта ошибка будет направлять ученика в подходящую Learning Path.\"\n        )\n'''
if 'async def start_task14_bank_pilot' not in text:
    if anchor not in text:
        raise SystemExit('anchor not found')
    text = text.replace(anchor, block + anchor, 1)

reg = '    dp.message.register(start_task14_learning_path_pilot, F.text == "/test_learning_path14")\n'
if 'F.text == "/test_task_bank14"' not in text:
    text = text.replace(reg, reg + '    dp.message.register(start_task14_bank_pilot, F.text == "/test_task_bank14")\n', 1)
reg2 = '    dp.message.register(receive_ege_tutor_pilot_answer, StudentEgeExamStates.waiting_tutor_pilot_answer)\n'
if 'waiting_task_bank_answer' not in text[text.find('def register_student_handlers'):]:
    text = text.replace(reg2, reg2 + '    dp.message.register(receive_task14_bank_answer, StudentEgeExamStates.waiting_task_bank_answer, F.text)\n', 1)
p.write_text(text, encoding='utf-8')

# Extend handler regression coverage.
t = Path('tests/test_student_diagnostic_handler_flow.py')
txt = t.read_text(encoding='utf-8')
if 'test_admin_can_issue_curated_task_bank14_item' not in txt:
    txt += '''\n\ndef test_admin_can_issue_curated_task_bank14_item(monkeypatch):\n    state = FakeState()\n    message = FakeMessage(user_id=42)\n    monkeypatch.setattr(student_handler, \"ADMIN_TELEGRAM_ID\", \"42\")\n    asyncio.run(student_handler.start_task14_bank_pilot(message, state))\n    assert state.data[\"task_bank_id\"] == \"reshuege-92256\"\n    assert any(\"Task Bank\" in item for item in message.answers)\n    assert any(\"№92256\" in item for item in message.answers)\n\n    answer = FakeMessage(user_id=42, text=\"71\")\n    asyncio.run(student_handler.receive_task14_bank_answer(answer, state))\n    assert any(\"Python-валидатор\" in item for item in answer.answers)\n    assert state.cleared is True\n'''
t.write_text(txt, encoding='utf-8')
