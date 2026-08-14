from pathlib import Path

p = Path('src/ai_engine/diagnostics.py')
text = p.read_text(encoding='utf-8')
anchor = '''CONTROL_PROBES = {\n'''
if anchor not in text:
    raise SystemExit('CONTROL_PROBES anchor missing')
# Insert transfer registry after CONTROL_PROBES dict, just before normalize helper.
marker = '''\n\ndef _normalize_probe_answer(value: str) -> str:\n'''
transfer = '''\n\n# A second local probe must use genuinely new data. Repeating the same question\n# cannot count as independent evidence for a Learning DNA weakness.\nPILOT_TRANSFER_PROBES = {\n    (5, 0): {"prompt": "Переведите число 23 в двоичную систему. Запишите только двоичную запись.", "expected_answers": ("10111",)},\n    (5, 1): {"prompt": "Алгоритм проверяет последнюю цифру двоичной записи: если она равна 1, справа дописывается 0; иначе дописывается 11. Для N=10 выберите применяемую ветку: ветка 1 или ветка 0.", "expected_answers": ("ветка 0", "0")},\n    (5, 2): {"prompt": "Для N=10 двоичная запись равна 1010. По правилу для последней цифры 0 справа дописывается 11. Запишите получившуюся двоичную строку.", "expected_answers": ("101011",)},\n    (5, 3): {"prompt": "Известно, что N=20 удовлетворяет условию поиска, а N=21 уже не удовлетворяет. Какое наибольшее целое N подходит?", "expected_answers": ("20",)},\n    (14, 0): {"prompt": "При переводе числа 725 в систему счисления с основанием 12 сначала делят 725 на 12. Какой остаток получится?", "expected_answers": ("5",)},\n    (14, 1): {"prompt": "В 16-ричной системе цифра F имеет значение 15. Учитывается ли F при подсчёте цифр с чётным числовым значением? Ответьте да или нет.", "expected_answers": ("нет", "no")},\n    (14, 2): {"prompt": "При переводе числа остатки получались в порядке 4, 1, 3. Последнее ненулевое частное равно 2. Запишите итоговую запись числа.", "expected_answers": ("2314",)},\n    (27, 0): {"prompt": "Даны точки (0,0), (0,3), (12,12), (15,12). Внутри каждой пары расстояние равно 3, а между парами значительно больше. Сколько явно разделённых кластеров получается по этим расстояниям?", "expected_answers": ("2",)},\n    (27, 1): {"prompt": "Для трёх точек одного кластера суммы расстояний до остальных равны: A — 9, B — 13, C — 6. Какая точка является медоидом?", "expected_answers": ("C", "С")},\n    (27, 2): {"prompt": "После кластеризации получены метки 1, 3, 3, 2, 3, 1. Сколько точек относится к кластеру с меткой 3?", "expected_answers": ("3",)},\n    (27, 3): {"prompt": "Расстояния от медоида до остальных точек кластера равны 6, 2 и 9. Каково максимальное расстояние?", "expected_answers": ("9",)},\n}\n'''
if 'PILOT_TRANSFER_PROBES = {' not in text:
    if marker not in text:
        raise SystemExit('normalize marker missing')
    text = text.replace(marker, transfer + marker, 1)

old = '''            result = {\n                "probe_id": probe["id"] if failure_count == 0 else f"{probe['id']}:retry{failure_count + 1}",\n                "base_probe_id": probe["id"],\n                "operation_index": operation_index,\n                "prompt": probe["prompt"],\n                "tested_step": operations[operation_index],\n                "probe_role": "discrimination" if failure_count == 0 else "transfer",\n            }\n'''
new = '''            transfer = PILOT_TRANSFER_PROBES.get((int(case.get("task_number", 0)), operation_index)) if failure_count else None\n            prompt = transfer["prompt"] if transfer else probe["prompt"]\n            expected_answers = transfer["expected_answers"] if transfer else probe["expected_answers"]\n            result = {\n                "probe_id": probe["id"] if failure_count == 0 else f"{probe['id']}:retry{failure_count + 1}",\n                "base_probe_id": probe["id"],\n                "operation_index": operation_index,\n                "prompt": prompt,\n                "expected_answers": expected_answers,\n                "tested_step": operations[operation_index],\n                "probe_role": "discrimination" if failure_count == 0 else "transfer",\n            }\n'''
if old not in text:
    raise SystemExit('next_control_probe result block missing')
text = text.replace(old, new, 1)

# Ensure pending restoration keeps expected answers and role, otherwise local fallback loses transfer contract.
old = '''                result.update({key: pending[key] for key in ("probe_id", "base_probe_id", "prompt", "source") if key in pending})\n'''
new = '''                result.update({key: pending[key] for key in ("probe_id", "base_probe_id", "prompt", "expected_answers", "probe_role", "source") if key in pending})\n'''
if old not in text:
    raise SystemExit('pending restore block missing')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# Regression: the exact live failure we observed must never confirm on a duplicated fallback question.
t = Path('tests/test_ege_diagnostics.py')
txt = t.read_text(encoding='utf-8')
addition = '''\n\ndef test_pilot_fallback_transfer_uses_new_question_and_new_data():\n    full_map = json.loads(\n        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")\n    )\n    for task_number in (5, 14, 27):\n        case = open_diagnostic_case(task_number, "wrong", "expected", full_map)\n        first = next_control_probe(case)\n        first_prompt = first["prompt"]\n        case = _answer_displayed_probe(case, first["probe_id"], "definitely-wrong")\n        second = next_control_probe(case)\n        assert second["probe_role"] == "transfer"\n        assert second["base_probe_id"] == first["base_probe_id"]\n        assert second["prompt"] != first_prompt\n        assert tuple(second["expected_answers"]) != tuple(first["expected_answers"]) or second["prompt"] != first_prompt\n\n\ndef test_task14_remainder_fallback_requires_two_distinct_questions_before_confirmation():\n    full_map = json.loads(\n        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")\n    )\n    case = open_diagnostic_case(14, "wrong", "expected", full_map)\n    first = next_control_probe(case)\n    case = _answer_displayed_probe(case, first["probe_id"], "34")\n    assert case["status"] != DIAGNOSIS_CONFIRMED\n    second = next_control_probe(case)\n    assert "725" in second["prompt"]\n    assert second["prompt"] != first["prompt"]\n    case = _answer_displayed_probe(case, second["probe_id"], "34")\n    assert case["status"] == DIAGNOSIS_CONFIRMED\n    failed = [e for e in case["evidence"] if e.get("kind") == "control_probe" and not e.get("is_correct")]\n    assert len({e.get("display_prompt") for e in failed[-2:]}) == 2\n'''
if 'test_pilot_fallback_transfer_uses_new_question_and_new_data' not in txt:
    txt += addition
t.write_text(txt, encoding='utf-8')
