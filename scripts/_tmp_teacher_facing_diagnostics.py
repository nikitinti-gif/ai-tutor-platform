from pathlib import Path

p = Path('src/services/ege_exam_service.py')
text = p.read_text(encoding='utf-8')
old = '''    for case in confirmed:\n        lines.append(\n            f"• Задание №{case['task_number']}: {case['failed_step']}"\n        )\n'''
new = '''    for case in confirmed:\n        confirmed_gap = next(\n            (item for item in case.get("gap_hypotheses", []) if item.get("status") == "confirmed"),\n            None,\n        )\n        if confirmed_gap:\n            lines.append(\n                f"• Задание №{case['task_number']}: {confirmed_gap['description']}"\n            )\n            lines.append(\n                f"  Что повторить: {confirmed_gap['required_rule']}"\n            )\n        else:\n            lines.append(\n                f"• Задание №{case['task_number']}: {case.get('failed_step') or 'точка ошибки подтверждена'}"\n            )\n'''
if old not in text:
    raise SystemExit('diagnostic_summary block not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

t = Path('tests/test_ege_diagnostics.py')
tests = t.read_text(encoding='utf-8')
addition = '''\n\ndef test_diagnostic_summary_uses_pedagogical_gap_instead_of_engineering_step():\n    full_map = json.loads(\n        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")\n    )\n    attempt = ExamAttempt()\n    case = open_diagnostic_case(27, "wrong", "expected", full_map)\n    gap = case["gap_hypotheses"][1]\n    case = record_control_probe(\n        case, probe_id="summary-medoid-a", tested_step=case["operations"][1], is_correct=False,\n        observed_answer="C", gap=gap, probe_role="discrimination"\n    )\n    case = record_control_probe(\n        case, probe_id="summary-medoid-b", tested_step=case["operations"][1], is_correct=False,\n        observed_answer="A", gap=gap, probe_role="transfer"\n    )\n    attempt.diagnostics[27] = case\n    summary = diagnostic_summary(attempt)\n    assert "Ошибается при выборе медоида по минимальной сумме расстояний." in summary\n    assert "Что повторить: Медоид — объект кластера" in summary\n    assert f"№27: {case['failed_step']}" not in summary\n'''
if 'test_diagnostic_summary_uses_pedagogical_gap_instead_of_engineering_step' not in tests:
    tests += addition
t.write_text(tests, encoding='utf-8')
