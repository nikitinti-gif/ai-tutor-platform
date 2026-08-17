from pathlib import Path

service = Path('src/services/ege_exam_service.py')
text = service.read_text(encoding='utf-8')

old14 = '''    elif stage == "verification":\n        # A failed blind check is evidence that the skill is not stable yet.\n        # Start a fresh teaching round instead of drilling the same question.\n        remediation["status"] = "remediating"\n        remediation["stage"] = "control"\n        remediation["control_attempts"] = 0\n        remediation["retest_attempts"] = 0\n        remediation["learning_round"] += 1\n'''
new14 = '''    elif stage == "verification":\n        # A failed blind check is evidence that the skill is not stable yet.\n        # Start a fresh teaching round instead of drilling the same question.\n        remediation["status"] = "remediating"\n        remediation["stage"] = "control"\n        remediation["control_attempts"] = 0\n        remediation["retest_attempts"] = 0\n        remediation["learning_round"] += 1\n    elif stage == "retest" and remediation["retest_attempts"] >= 2:\n        # Repeating the same transfer question is not teaching. After two\n        # failed attempts return to a fresh explanation/control round.\n        remediation["status"] = "remediating"\n        remediation["stage"] = "control"\n        remediation["control_attempts"] = 0\n        remediation["retest_attempts"] = 0\n        remediation["learning_round"] += 1\n'''
if old14 not in text:
    raise SystemExit('task14 remediation block not found')
text = text.replace(old14, new14, 1)

old27 = '''    elif stage == "verification":\n        remediation["status"] = "remediating"; remediation["stage"] = "control"\n        remediation["control_attempts"] = 0; remediation["retest_attempts"] = 0; remediation["verification_attempts"] = 0\n        remediation["learning_round"] += 1\n'''
new27 = '''    elif stage == "verification":\n        remediation["status"] = "remediating"; remediation["stage"] = "control"\n        remediation["control_attempts"] = 0; remediation["retest_attempts"] = 0; remediation["verification_attempts"] = 0\n        remediation["learning_round"] += 1\n    elif stage == "retest" and remediation["retest_attempts"] >= 2:\n        # Never drill the same transfer prompt indefinitely. Two failed\n        # attempts mean the explanation did not transfer; reteach instead.\n        remediation["status"] = "remediating"; remediation["stage"] = "control"\n        remediation["control_attempts"] = 0; remediation["retest_attempts"] = 0; remediation["verification_attempts"] = 0\n        remediation["learning_round"] += 1\n'''
if old27 not in text:
    raise SystemExit('task27 remediation block not found')
text = text.replace(old27, new27, 1)
service.write_text(text, encoding='utf-8')

handler = Path('src/telegram_bot/handlers/student.py')
text = handler.read_text(encoding='utf-8')
old = '''    elif result["stage"] == "control" and attempt.remediation.get("learning_round", 1) > 1:\n        await message.answer(\n            "Эта независимая задача показала, что правило пока не стало "\n            "устойчивым. Это нормально: разберём его другим способом и "\n            "попробуем снова на новых данных."\n        )\n'''
new = '''    elif result["stage"] == "control" and attempt.remediation.get("learning_round", 1) > 1:\n        await message.answer(\n            "Похоже, одной подсказки недостаточно. Не будем повторять один и тот же "\n            "вопрос. Вернёмся к правилу, разберём его ещё раз и затем проверим на новых данных."\n        )\n'''
if old not in text:
    raise SystemExit('handler reteach message block not found')
text = text.replace(old, new, 1)
handler.write_text(text, encoding='utf-8')

test = Path('tests/test_task27_remediation.py')
t = test.read_text(encoding='utf-8')
addition = '''\n\ndef test_task27_retest_does_not_repeat_forever_after_two_wrong_answers():\n    from src.services.ege_exam_service import ExamAttempt, submit_task27_remediation_answer\n    attempt = ExamAttempt()\n    attempt.remediation = {\n        "task_number": 27,\n        "skill_id": "programming.cluster_count_from_separation",\n        "status": "remediating",\n        "stage": "retest",\n        "control_attempts": 1,\n        "retest_attempts": 0,\n        "verification_attempts": 0,\n        "learning_round": 1,\n        "stage_history": [],\n    }\n    first = submit_task27_remediation_answer(attempt, "1")\n    assert first["is_correct"] is False\n    assert attempt.remediation["stage"] == "retest"\n    second = submit_task27_remediation_answer(attempt, "2")\n    assert second["is_correct"] is False\n    assert attempt.remediation["stage"] == "control"\n    assert attempt.remediation["learning_round"] == 2\n    assert attempt.remediation["retest_attempts"] == 0\n'''
if 'test_task27_retest_does_not_repeat_forever_after_two_wrong_answers' not in t:
    t += addition
test.write_text(t, encoding='utf-8')

# Add equivalent protection for task 14 so the same UX bug cannot reappear there.
test14 = Path('tests/test_ege_diagnostics.py')
t14 = test14.read_text(encoding='utf-8')
addition14 = '''\n\ndef test_task14_retest_returns_to_teaching_after_two_wrong_answers():\n    from src.services.ege_exam_service import ExamAttempt, submit_task14_remediation_answer\n    attempt = ExamAttempt()\n    attempt.remediation = {\n        "task_number": 14,\n        "gap_id": "BASE_REMAINDER_EXTRACTION",\n        "status": "remediating",\n        "stage": "retest",\n        "control_attempts": 1,\n        "retest_attempts": 0,\n        "verification_attempts": 0,\n        "learning_round": 1,\n        "stage_history": [],\n    }\n    submit_task14_remediation_answer(attempt, "wrong")\n    result = submit_task14_remediation_answer(attempt, "still-wrong")\n    assert result["is_correct"] is False\n    assert attempt.remediation["stage"] == "control"\n    assert attempt.remediation["learning_round"] == 2\n'''
if 'test_task14_retest_returns_to_teaching_after_two_wrong_answers' not in t14:
    t14 += addition14
test14.write_text(t14, encoding='utf-8')
