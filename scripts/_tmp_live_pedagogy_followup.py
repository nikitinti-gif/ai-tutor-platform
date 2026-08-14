from pathlib import Path

# 1) Do not confuse knowing the medoid criterion with the requested answer format.
p = Path('src/ai_engine/diagnostics.py')
text = p.read_text(encoding='utf-8')
text = text.replace(
    '{"id": "task27_medoid_v2", "operation_index": 1, "prompt": "Для трёх точек одного кластера суммы расстояний до остальных равны: A — 8, B — 5, C — 7. Какая точка является медоидом?", "expected_answers": ("B", "Б")}',
    '{"id": "task27_medoid_v2", "operation_index": 1, "prompt": "Для трёх точек одного кластера суммы расстояний до остальных равны: A — 8, B — 5, C — 7. Какая точка является медоидом? Ответьте буквой A, B или C.", "expected_answers": ("B", "Б", "5")}'
)
text = text.replace(
    '(27, 1): {"prompt": "Для трёх точек одного кластера суммы расстояний до остальных равны: A — 9, B — 13, C — 6. Какая точка является медоидом?", "expected_answers": ("C", "С")}',
    '(27, 1): {"prompt": "Для трёх точек одного кластера суммы расстояний до остальных равны: A — 9, B — 13, C — 6. Какая точка является медоидом? Ответьте буквой A, B или C.", "expected_answers": ("C", "С", "6")}'
)
p.write_text(text, encoding='utf-8')

# 2) Live AI probes: accept the minimum numeric sum as evidence of the same atomic concept.
p = Path('src/ai_engine/live_diagnostic_probes.py')
text = p.read_text(encoding='utf-8')
old = '''    expected_answers = (str(answer),)\n    if (task, operation) == (5, 1): expected_answers = (str(answer), f"ветка {answer}")\n'''
new = '''    expected_answers = (str(answer),)\n    if (task, operation) == (5, 1):\n        expected_answers = (str(answer), f"ветка {answer}")\n    elif (task, operation) == (27, 1):\n        sums = [int(value) for value in re.findall(r"\\d+", str(fields["sums"]))]\n        expected_answers = (str(answer), str(min(sums)))\n'''
if old not in text:
    raise SystemExit('live expected answer block not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# 3) Remediation checks concept, while wording still teaches exam-format labels.
p = Path('src/services/ege_exam_service.py')
text = p.read_text(encoding='utf-8')
replacements = {
    '"control_prompt": "Контроль: суммы A=14, B=11, C=17. Какой медоид выбрать?",\n        "control_answers": ("B", "Б"),': '"control_prompt": "Контроль: суммы A=14, B=11, C=17. Какой медоид выбрать? Ответь буквой A, B или C.",\n        "control_answers": ("B", "Б", "11"),',
    '"retest_prompt": "Перенос: суммы A=21, B=16, C=19. Какой медоид оптимален?",\n        "retest_answers": ("B", "Б"),': '"retest_prompt": "Перенос: суммы A=21, B=16, C=19. Какой медоид оптимален? Ответь буквой A, B или C.",\n        "retest_answers": ("B", "Б", "16"),',
    '"verification_prompt": "Независимая проверка: суммы A=18, B=23, C=15. Какой медоид оптимален?",\n        "verification_answers": ("C", "С"),': '"verification_prompt": "Независимая проверка: суммы A=18, B=23, C=15. Какой медоид оптимален? Ответь буквой A, B или C.",\n        "verification_answers": ("C", "С", "15"),',
}
for old, new in replacements.items():
    if old not in text:
        raise SystemExit('task27 remediation block not found: ' + old[:50])
    text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# 4) Telegram feedback must name the actual task, never hard-code №14.
p = Path('src/telegram_bot/handlers/student.py')
text = p.read_text(encoding='utf-8')
old = '''        await message.answer(\n            "✅ Верно. Теперь проверим, сможешь ли ты применить это правило "\n            "в новой задаче типа №14."\n        )\n'''
new = '''        await message.answer(\n            "✅ Верно. Теперь проверим, сможешь ли ты применить это правило "\n            f"на новых данных по заданию №{remediation_task}."\n        )\n'''
if old not in text:
    raise SystemExit('hard-coded №14 feedback not found')
text = text.replace(old, new, 1)
old = '''    next_focus = dna.get("trajectory", {}).get("next_focus")\n'''
new = '''    next_focus = (plan[0].get("skill_name") if plan else None) or dna.get("trajectory", {}).get("next_focus")\n'''
if old not in text:
    raise SystemExit('next_focus display line not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# Regression protection for live findings.
t = Path('tests/test_pilot_full_telegram_loop.py')
txt = t.read_text(encoding='utf-8')
addition = '''\n\ndef test_task27_medoid_numeric_minimum_is_not_misdiagnosed_as_concept_gap(monkeypatch):\n    sessions = {}\n    dna_store = {}\n    _patch_storage(monkeypatch, sessions, dna_store)\n    from src.services.ege_exam_service import ExamAttempt, bind_current_diagnostic_probe, mark_current_diagnostic_probe_displayed, submit_diagnostic_answer\n    from src.ai_engine.diagnostics import open_diagnostic_case\n    from src.skills.skill_graph import load_skill_map\n    attempt = ExamAttempt()\n    attempt.diagnostics = {27: open_diagnostic_case(27, "wrong", "expected", load_skill_map())}\n    bind_current_diagnostic_probe(attempt); mark_current_diagnostic_probe_displayed(attempt)\n    submit_diagnostic_answer(attempt, "2")\n    bind_current_diagnostic_probe(attempt); mark_current_diagnostic_probe_displayed(attempt)\n    result = submit_diagnostic_answer(attempt, "5")\n    assert result["is_correct"] is True\n    assert attempt.diagnostics[27]["status"] != "confirmed"\n\n\ndef test_task27_remediation_accepts_numeric_minimum_as_concept_evidence():\n    from src.services.ege_exam_service import ExamAttempt, submit_task27_remediation_answer\n    attempt = ExamAttempt()\n    attempt.remediation = {\n        "task_number": 27, "skill_id": "programming.medoid_minimum", "status": "remediating", "stage": "control",\n        "control_attempts": 0, "retest_attempts": 0, "verification_attempts": 0, "learning_round": 1, "stage_history": []\n    }\n    result = submit_task27_remediation_answer(attempt, "11")\n    assert result["is_correct"] is True\n    assert attempt.remediation["stage"] == "retest"\n'''
if 'test_task27_medoid_numeric_minimum_is_not_misdiagnosed_as_concept_gap' not in txt:
    txt += addition
t.write_text(txt, encoding='utf-8')

# Existing live-probe contract now intentionally accepts both the label and the minimum sum.
t = Path('tests/test_ege_diagnostics.py')
txt = t.read_text(encoding='utf-8')
txt = txt.replace('assert generated["expected_answers"] == ("B",)', 'assert generated["expected_answers"] == ("B", "5")')
t.write_text(txt, encoding='utf-8')
