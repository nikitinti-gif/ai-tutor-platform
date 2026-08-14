from pathlib import Path

p = Path('src/services/ege_exam_service.py')
text = p.read_text(encoding='utf-8')
old = '''    return {\n        "task_number": task_number,\n        "probe_id": probe["probe_id"],\n        "is_correct": evidence["is_correct"],\n        "status": case["status"],\n        "failed_step": case.get("failed_step"),\n        "gap_id": evidence.get("gap_id"),\n        "probe_role": evidence.get("probe_role"),\n    }\n'''
new = '''    confirmed_gap = next(\n        (item for item in case.get("gap_hypotheses", []) if item.get("status") == "confirmed"),\n        None,\n    )\n    return {\n        "task_number": task_number,\n        "probe_id": probe["probe_id"],\n        "is_correct": evidence["is_correct"],\n        "status": case["status"],\n        "failed_step": case.get("failed_step"),\n        "gap_id": evidence.get("gap_id"),\n        "probe_role": evidence.get("probe_role"),\n        "diagnosis": confirmed_gap.get("description") if confirmed_gap else None,\n        "required_rule": confirmed_gap.get("required_rule") if confirmed_gap else None,\n    }\n'''
if old not in text:
    raise SystemExit('submit_diagnostic_answer return block not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

p = Path('src/telegram_bot/handlers/student.py')
text = p.read_text(encoding='utf-8')
old = '''    elif result["status"] == "confirmed":\n        await message.answer(\n            "🔴 Точка ошибки подтверждена локальной пробой:\\n"\n            f"{result['failed_step']}"\n        )\n'''
new = '''    elif result["status"] == "confirmed":\n        diagnosis = result.get("diagnosis") or result.get("failed_step") or "Точка ошибки подтверждена."\n        rule = result.get("required_rule")\n        text = "🔴 Точка ошибки подтверждена двумя независимыми пробами:\\n" + diagnosis\n        if rule:\n            text += "\\n\\n📌 Что нужно повторить:\\n" + rule\n        await message.answer(text)\n'''
if old not in text:
    raise SystemExit('student confirmed message block not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

p = Path('tests/test_pilot_full_telegram_loop.py')
text = p.read_text(encoding='utf-8')
needle = '''    assert any("КОРОТКОЕ ОБУЧЕНИЕ · №14" in text for text in transcript)\n'''
replacement = needle + '''    assert any("Точка ошибки подтверждена двумя независимыми пробами" in text for text in transcript)\n    assert any("Что нужно повторить:" in text for text in transcript)\n    assert any("Ошибается при вычислении остатка" in text for text in transcript)\n'''
if 'Точка ошибки подтверждена двумя независимыми пробами' not in text:
    if needle not in text:
        raise SystemExit('telegram assertion insertion point not found')
    text = text.replace(needle, replacement, 1)
p.write_text(text, encoding='utf-8')
