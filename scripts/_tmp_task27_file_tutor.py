from pathlib import Path

# 1) Add exam-file service helpers next to the task-first pilot helpers.
p = Path('src/services/ege_exam_service.py')
text = p.read_text(encoding='utf-8')
needle = '''def create_task_first_tutor_attempt() -> ExamAttempt:\n    """Create an empty pilot attempt; cases are opened only after real mistakes."""\n    return ExamAttempt(current_task=TOTAL_TASKS + 1)\n'''
addition = '''TASK27_FILE_STAGE_META = {\n    "task27_file_a": {\n        "path": "Доп. файлы/1_27_A.txt",\n        "filename": "1_27_A.txt",\n        "title": "Файл A · настоящий формат КЕГЭ №27",\n    },\n    "task27_file_b": {\n        "path": "Доп. файлы/1_27_B.txt",\n        "filename": "1_27_B.txt",\n        "title": "Файл Б · настоящий формат КЕГЭ №27",\n    },\n}\n\n\ndef render_tutor_pilot_task27_file_stage(stage: str) -> str:\n    if stage == "task27_file_a":\n        return (\n            "━━━━━━━━━━━━━━━━━━━━\\n"\n            "📁 ПРАКТИКА С ФАЙЛОМ · КЕГЭ №27\\n"\n            "━━━━━━━━━━━━━━━━━━━━\\n\\n"\n            "Теперь не игрушечные три точки, а настоящий файл открытого варианта 2026.\\n\\n"\n            "В файле A находятся точки двух кластеров. Для каждого кластера H=6,0 и W=5,5. "\n            "Центр кластера — одна из его точек, у которой сумма расстояний до остальных точек минимальна.\\n\\n"\n            "Найди кластер с наименьшим числом точек. Среди красных гигантов этого кластера "\n            "(спектральный класс M, класс светимости III) найди звезду, ближайшую к центру.\\n\\n"\n            "Ответ: два целых числа — целые части |Ax·10000| и |Ay·10000| через пробел.\\n\\n"\n            "Подсказка по организации решения: сначала прочитай файл и визуализируй точки; "\n            "после разбиения вычисляй центр перебором точек самого кластера. Сам ответ Python Tutor не показывает."\n        )\n    if stage == "task27_file_b":\n        return (\n            "━━━━━━━━━━━━━━━━━━━━\\n"\n            "🎯 БЕЗ УЧЕБНОГО ПРИМЕРА · КЕГЭ №27\\n"\n            "━━━━━━━━━━━━━━━━━━━━\\n\\n"\n            "Файл Б содержит три кластера (H=6,0; W=5,5). Центр определяется так же — "\n            "как точка кластера с минимальной суммой расстояний.\\n\\n"\n            "B1: найди расстояние между центрами кластеров с наименьшим и наибольшим "\n            "количеством оранжевых гигантов (K + III).\\n"\n            "B2: найди наибольшее расстояние между жёлтыми карликами (G + V), "\n            "принадлежащими одному кластеру.\\n\\n"\n            "Ответ: целые части B1·10000 и B2·10000 через пробел."\n        )\n    raise ValueError("Неизвестный этап файловой практики №27.")\n\n\ndef verify_tutor_pilot_task27_file_answer(stage: str, answer: str) -> bool:\n    from src.services.ege_task27_service import (\n        normalize_two_number_answer, solve_open_variant_a, solve_open_variant_b,\n    )\n    normalized = normalize_two_number_answer(answer)\n    if normalized is None:\n        return False\n    if stage == "task27_file_a":\n        expected = solve_open_variant_a()["answer"]\n    elif stage == "task27_file_b":\n        expected = solve_open_variant_b()["answer"]\n    else:\n        raise ValueError("Неизвестный этап файловой практики №27.")\n    return normalized == expected\n\n\ndef record_tutor_pilot_task27_file_answer(\n    attempt: ExamAttempt, stage: str, answer: str\n) -> bool:\n    from src.services.ege_task27_service import solve_open_variant_a, solve_open_variant_b\n    is_correct = verify_tutor_pilot_task27_file_answer(stage, answer)\n    expected = (\n        solve_open_variant_a()["answer"]\n        if stage == "task27_file_a"\n        else solve_open_variant_b()["answer"]\n    )\n    attempt.answers[27] = answer\n    attempt.results[27] = is_correct\n    if not is_correct:\n        attempt.diagnostics[27] = open_diagnostic_case(\n            task_number=27,\n            student_answer=answer,\n            expected_answer=" ".join(map(str, expected)),\n            skill_map=load_skill_map(),\n        )\n    else:\n        attempt.diagnostics.pop(27, None)\n    return is_correct\n\n\n'''
if 'TASK27_FILE_STAGE_META' not in text:
    if needle not in text:
        raise SystemExit('service insertion point not found')
    text = text.replace(needle, addition + needle, 1)
p.write_text(text, encoding='utf-8')

# 2) Wire the file stages into Telegram.
p = Path('src/telegram_bot/handlers/student.py')
text = p.read_text(encoding='utf-8')
handler_needle = '''async def start_ege_tutor_pilot(message: Message, state: FSMContext):\n'''
helper = '''async def _send_tutor_task27_file_stage(message: Message, stage: str) -> None:\n    from src.services.ege_exam_service import TASK27_FILE_STAGE_META, render_tutor_pilot_task27_file_stage\n    meta = TASK27_FILE_STAGE_META[stage]\n    await message.answer_document(\n        document=FSInputFile(meta["path"], filename=meta["filename"]),\n        caption=meta["title"],\n    )\n    await message.answer(render_tutor_pilot_task27_file_stage(stage))\n\n\n'''
if '_send_tutor_task27_file_stage' not in text:
    if handler_needle not in text:
        raise SystemExit('handler helper insertion point not found')
    text = text.replace(handler_needle, helper + handler_needle, 1)

old_import = '''        record_tutor_pilot_transfer_answer,\n        render_tutor_pilot_task,\n        render_tutor_pilot_transfer_task,\n    )\n'''
new_import = '''        record_tutor_pilot_transfer_answer,\n        record_tutor_pilot_task27_file_answer,\n        render_tutor_pilot_task,\n        render_tutor_pilot_transfer_task,\n    )\n'''
if old_import not in text:
    raise SystemExit('tutor receive import block not found')
text = text.replace(old_import, new_import, 1)

stage_needle = '''    task_number = tasks[index]\n\n    if stage == "supported":\n'''
stage_block = '''    task_number = tasks[index]\n\n    if stage in {"task27_file_a", "task27_file_b"}:\n        is_correct = record_tutor_pilot_task27_file_answer(\n            attempt, stage, message.text or ""\n        )\n        if not is_correct:\n            await message.answer(\n                "❌ На настоящем файле возникла ошибка. Не буду давать следующий большой файл: "\n                "сначала локализуем конкретный шаг, который требует помощи."\n            )\n            await state.update_data(ege_attempt=attempt.to_dict())\n            save_ege_session(\n                message.from_user.id, attempt.to_dict(), status="tutor_pilot_in_progress"\n            )\n            await _begin_ege_diagnostics(message, state, attempt)\n            return\n        if stage == "task27_file_a":\n            await message.answer(\n                "✅ Файл A решён верно. Теперь второй уровень: файл Б уже без учебного плана решения."\n            )\n            await state.update_data(\n                ege_attempt=attempt.to_dict(), tutor_pilot_stage="task27_file_b"\n            )\n            save_ege_session(\n                message.from_user.id, attempt.to_dict(), status="tutor_pilot_in_progress"\n            )\n            await _send_tutor_task27_file_stage(message, "task27_file_b")\n            return\n        save_ege_session(message.from_user.id, attempt.to_dict(), status="completed")\n        await state.clear()\n        await message.answer(\n            "🏆 №27 пройден до настоящего файлового уровня: учебный пример → перенос → "\n            "официальный файл A → официальный файл Б. Диагностика не понадобилась."\n        )\n        return\n\n    if stage == "supported":\n'''
if stage_needle not in text:
    raise SystemExit('tutor stage insertion point not found')
text = text.replace(stage_needle, stage_block, 1)

old_transfer = '''    else:\n        is_correct = record_tutor_pilot_transfer_answer(attempt, task_number, message.text or "")\n        if is_correct:\n            await message.answer("✅ Получилось и без подсказки. Этот навык пока не требует диагностики.")\n        else:\n            await message.answer("❌ На новой задаче без подсказки возникла ошибка. После пилота разберём, на каком шаге она появилась.")\n\n    index += 1\n'''
new_transfer = '''    else:\n        is_correct = record_tutor_pilot_transfer_answer(attempt, task_number, message.text or "")\n        if is_correct:\n            if task_number == 27:\n                await message.answer(\n                    "✅ Маленькая задача без подсказки решена. Теперь проверяем сам формат №27 — с настоящим файлом."\n                )\n                await state.update_data(\n                    ege_attempt=attempt.to_dict(), tutor_pilot_stage="task27_file_a"\n                )\n                save_ege_session(\n                    message.from_user.id, attempt.to_dict(), status="tutor_pilot_in_progress"\n                )\n                await _send_tutor_task27_file_stage(message, "task27_file_a")\n                return\n            await message.answer("✅ Получилось и без подсказки. Этот навык пока не требует диагностики.")\n        else:\n            await message.answer("❌ На новой задаче без подсказки возникла ошибка. После пилота разберём, на каком шаге она появилась.")\n\n    index += 1\n'''
if old_transfer not in text:
    raise SystemExit('transfer branch not found')
text = text.replace(old_transfer, new_transfer, 1)
p.write_text(text, encoding='utf-8')

# 3) Extend service-level regression tests.
p = Path('tests/test_ege_tutor_pilot.py')
tests = p.read_text(encoding='utf-8')
tests = tests.replace(
    '    record_tutor_pilot_transfer_answer,\n)',
    '    record_tutor_pilot_transfer_answer,\n    record_tutor_pilot_task27_file_answer,\n    render_tutor_pilot_task27_file_stage,\n)',
    1,
)
addition = '''\n\ndef test_task27_real_file_stage_uses_official_data_and_python_reference_solver():\n    attempt = create_task_first_tutor_attempt()\n    rendered_a = render_tutor_pilot_task27_file_stage("task27_file_a")\n    rendered_b = render_tutor_pilot_task27_file_stage("task27_file_b")\n    assert "настоящий файл" in rendered_a.lower()\n    assert "красных гигантов" in rendered_a\n    assert "оранжевых гигантов" in rendered_b\n    assert "жёлтыми карликами" in rendered_b\n    assert record_tutor_pilot_task27_file_answer(attempt, "task27_file_a", "44694 69754") is True\n    assert 27 not in attempt.diagnostics\n    assert record_tutor_pilot_task27_file_answer(attempt, "task27_file_b", "138716 34029") is True\n    assert 27 not in attempt.diagnostics\n\n\ndef test_task27_real_file_error_opens_diagnostic_case():\n    attempt = create_task_first_tutor_attempt()\n    assert record_tutor_pilot_task27_file_answer(attempt, "task27_file_a", "1 2") is False\n    assert 27 in attempt.diagnostics\n    assert attempt.diagnostics[27]["expected_answer"] == "44694 69754"\n'''
if 'test_task27_real_file_stage_uses_official_data_and_python_reference_solver' not in tests:
    tests += addition
p.write_text(tests, encoding='utf-8')

# 4) Update stale regressions to the already-shipped no-gap-fishing/student wording behaviour.
p = Path('tests/test_student_diagnostic_handler_flow.py')
tests = p.read_text(encoding='utf-8')
tests = tests.replace('Пилот мини-проб №5, №14 и №27', 'Пилот разбора ошибок №5, №14 и №27')
p.write_text(tests, encoding='utf-8')

p = Path('tests/test_pilot_full_telegram_loop.py')
tests = p.read_text(encoding='utf-8')
tests = tests.replace('Пилот мини-проб №5, №14 и №27', 'Пилот разбора ошибок №5, №14 и №27')
old = '''def test_task27_medoid_numeric_minimum_is_not_misdiagnosed_as_concept_gap(monkeypatch):\n    sessions = {}\n    dna_store = {}\n    _patch_storage(monkeypatch, sessions, dna_store)\n    from src.services.ege_exam_service import ExamAttempt, bind_current_diagnostic_probe, mark_current_diagnostic_probe_displayed, submit_diagnostic_answer\n    from src.ai_engine.diagnostics import open_diagnostic_case\n    from src.skills.skill_graph import load_skill_map\n    attempt = ExamAttempt()\n    attempt.diagnostics = {27: open_diagnostic_case(27, "wrong", "expected", load_skill_map())}\n    bind_current_diagnostic_probe(attempt); mark_current_diagnostic_probe_displayed(attempt)\n    submit_diagnostic_answer(attempt, "2")\n    bind_current_diagnostic_probe(attempt); mark_current_diagnostic_probe_displayed(attempt)\n    result = submit_diagnostic_answer(attempt, "5")\n    assert result["is_correct"] is True\n    assert attempt.diagnostics[27]["status"] != "confirmed"\n\n\n'''
new = '''def test_task27_correct_first_probe_stops_before_unrelated_center_probe(monkeypatch):\n    sessions = {}\n    dna_store = {}\n    _patch_storage(monkeypatch, sessions, dna_store)\n    from src.services.ege_exam_service import ExamAttempt, bind_current_diagnostic_probe, mark_current_diagnostic_probe_displayed, next_attempt_diagnostic_probe, submit_diagnostic_answer\n    from src.ai_engine.diagnostics import open_diagnostic_case\n    from src.skills.skill_graph import load_skill_map\n    attempt = ExamAttempt()\n    attempt.diagnostics = {27: open_diagnostic_case(27, "wrong", "expected", load_skill_map())}\n    bind_current_diagnostic_probe(attempt); mark_current_diagnostic_probe_displayed(attempt)\n    result = submit_diagnostic_answer(attempt, "2")\n    assert result["is_correct"] is True\n    assert attempt.diagnostics[27]["status"] != "confirmed"\n    assert next_attempt_diagnostic_probe(attempt) is None\n\n\n'''
if old not in tests:
    raise SystemExit('obsolete task27 telegram test block not found')
tests = tests.replace(old, new, 1)
p.write_text(tests, encoding='utf-8')
