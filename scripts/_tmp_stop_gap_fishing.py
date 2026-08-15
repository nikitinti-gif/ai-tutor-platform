from pathlib import Path

# 1) Stop 'gap fishing': a correct probe disproves the current hypothesis for this task.
p = Path('src/ai_engine/diagnostics.py')
text = p.read_text(encoding='utf-8')
old = '''def next_control_probe(case: dict) -> dict | None:\n    \"\"\"Return the next unchecked local probe for a diagnostic case.\"\"\"\n    probes = CONTROL_PROBES.get(int(case.get(\"task_number\", 0)), ())\n    completed = {\n        item.get(\"base_probe_id\", item.get(\"probe_id\"))\n        for item in case.get(\"evidence\", [])\n        if item.get(\"kind\") == \"control_probe\" and item.get(\"is_correct\")\n    }\n'''
new = '''def next_control_probe(case: dict) -> dict | None:\n    \"\"\"Return the next probe without searching for a weakness at random.\n\n    With only a wrong final answer we do not know which later micro-step failed.\n    One correct diagnostic probe is therefore enough to reject the current\n    hypothesis and stop probing this task. A confirmed weakness still requires\n    two independent failed probes of the same atomic skill.\n    \"\"\"\n    probes = CONTROL_PROBES.get(int(case.get(\"task_number\", 0)), ())\n    if any(\n        item.get(\"kind\") == \"control_probe\" and item.get(\"is_correct\") is True\n        for item in case.get(\"evidence\", [])\n    ):\n        return None\n    completed = {\n        item.get(\"base_probe_id\", item.get(\"probe_id\"))\n        for item in case.get(\"evidence\", [])\n        if item.get(\"kind\") == \"control_probe\" and item.get(\"is_correct\")\n    }\n'''
if old not in text:
    raise SystemExit('next_control_probe header not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# 2) Student UX: show a tutor, not the internal diagnostic engine.
p = Path('src/services/ege_exam_service.py')
text = p.read_text(encoding='utf-8')
start = text.index('def render_diagnostic_probe(attempt: ExamAttempt) -> str:\n')
end = text.index('\n\ndef diagnostic_summary(attempt: ExamAttempt) -> str:\n', start)
new_func = '''def render_diagnostic_probe(attempt: ExamAttempt) -> str:\n    \"\"\"Render a concise teacher-facing probe; keep audit details internal.\"\"\"\n    probe = next_attempt_diagnostic_probe(attempt)\n    if probe is None:\n        return \"\"\n\n    role_text = {\n        \"discrimination\": \"Короткая проверка: хочу понять, случайной ли была ошибка.\",\n        \"transfer\": \"Проверка на новых данных: тот же навык, но другая задача.\",\n    }.get(probe.get(\"probe_role\"), \"Проверим один конкретный шаг решения.\")\n    return (\n        \"━━━━━━━━━━━━━━━━━━━━\\n\"\n        \"🔎 РАЗБЕРЁМ ОШИБКУ\\n\"\n        \"━━━━━━━━━━━━━━━━━━━━\\n\\n\"\n        f\"Задание КЕГЭ №{probe['task_number']}\\n\"\n        f\"{role_text}\\n\\n\"\n        f\"{probe['prompt']}\\n\\n\"\n        \"✍️ Отправь только ответ.\"\n    )\n'''
text = text[:start] + new_func + text[end:]
p.write_text(text, encoding='utf-8')

# 3) Telegram wording: explain the evidence-first policy and never promise random step hunting.
p = Path('src/telegram_bot/handlers/student.py')
text = p.read_text(encoding='utf-8')
old = '''    mode_text = (\n        \"AI создаёт новую формулировку и данные, а Python независимо проверяет вопрос и ответ.\"\n        if AI_DIAGNOSTIC_PROBES_ENABLED\n        and ADMIN_TELEGRAM_ID\n        and str(message.from_user.id) == str(ADMIN_TELEGRAM_ID)\n        else \"Каждая мини-проба проверяется локально.\"\n    )\n    await message.answer(\n        \"Теперь разберём только ошибочные задания. \" + mode_text\n    )\n'''
new = '''    await message.answer(\n        \"Теперь разберём только ошибочные задания. Сначала проверю один \"\n        \"конкретный навык. Если он выполнен верно, не буду искать пробел \"\n        \"наугад — перейдём к следующему заданию. Ответ всегда проверяет Python.\"\n    )\n'''
if old not in text:
    raise SystemExit('diagnostic intro block not found')
text = text.replace(old, new, 1)
old = '''    if result[\"is_correct\"]:\n        await message.answer(\n            \"✅ Этот шаг выполнен верно — гипотеза об ошибке не подтверждена. \"\n            \"Проверяем следующий шаг этого же задания.\"\n        )\n'''
new = '''    if result[\"is_correct\"]:\n        await message.answer(\n            \"✅ Этот навык выполнен верно. Пробел не подтверждён, поэтому \"\n            \"не будем искать другую слабость наугад и перейдём дальше.\"\n        )\n'''
if old not in text:
    raise SystemExit('correct diagnostic feedback not found')
text = text.replace(old, new, 1)
old = '''    await message.answer(\n        \"🧪 Пилот мини-проб №5, №14 и №27.\\n\\n\"\n        \"Полный вариант проходить не нужно. Ответы проверяются локально.\"\n    )\n'''
new = '''    await message.answer(\n        \"🧪 Пилот разбора ошибок №5, №14 и №27.\\n\\n\"\n        \"Полный вариант проходить не нужно. Это проверка логики репетитора: \"\n        \"не приписываем пробел без доказательств и не гоняем ученика по всем \"\n        \"микрошагам задания.\"\n    )\n'''
if old not in text:
    raise SystemExit('pilot intro not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# 4) Regression tests for the live pedagogical finding.
t = Path('tests/test_ege_diagnostics.py')
txt = t.read_text(encoding='utf-8')
addition = '''\n\ndef test_correct_probe_stops_task_instead_of_gap_fishing():\n    full_map = json.loads(\n        (Path(__file__).parents[1] / \"src\" / \"skills\" / \"ege_informatics_2026.json\").read_text(encoding=\"utf-8\")\n    )\n    case = open_diagnostic_case(5, \"wrong\", \"expected\", full_map)\n    first = next_control_probe(case)\n    case = record_control_probe(\n        case, probe_id=first[\"probe_id\"], tested_step=first[\"tested_step\"],\n        is_correct=True, observed_answer=\"10011\",\n        gap=case[\"gap_hypotheses\"][0], probe_role=\"discrimination\"\n    )\n    assert next_control_probe(case) is None\n    assert case[\"status\"] != DIAGNOSIS_CONFIRMED\n\n\ndef test_rendered_probe_hides_internal_audit_language():\n    from src.services.ege_exam_service import ExamAttempt, render_diagnostic_probe\n    full_map = json.loads(\n        (Path(__file__).parents[1] / \"src\" / \"skills\" / \"ege_informatics_2026.json\").read_text(encoding=\"utf-8\")\n    )\n    attempt = ExamAttempt()\n    attempt.diagnostics = {14: open_diagnostic_case(14, \"wrong\", \"expected\", full_map)}\n    rendered = render_diagnostic_probe(attempt)\n    assert \"Гипотеза:\" not in rendered\n    assert \"Почему эта проба подходит\" not in rendered\n    assert \"Источник:\" not in rendered\n    assert \"1298\" in rendered\n'''
if 'test_correct_probe_stops_task_instead_of_gap_fishing' not in txt:
    txt += addition
t.write_text(txt, encoding='utf-8')

# Existing tests that explicitly expected the old gap-fishing behavior are no longer valid.
for test_path in ['tests/test_pilot_full_student_loop.py', 'tests/test_pilot_full_telegram_loop.py']:
    p = Path(test_path)
    if not p.exists():
        continue
    s = p.read_text(encoding='utf-8')
    s = s.replace('assert 5 in attempt.diagnostics', 'assert 5 in attempt.diagnostics')
    p.write_text(s, encoding='utf-8')
