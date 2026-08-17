from pathlib import Path

# 1) Let diagnostic cases optionally define an ordered, task-relevant probe path.
p = Path('src/ai_engine/diagnostics.py')
text = p.read_text(encoding='utf-8')
old = '''    probes = CONTROL_PROBES.get(int(case.get("task_number", 0)), ())\n    if any(\n        item.get("kind") == "control_probe" and item.get("is_correct") is True\n        for item in case.get("evidence", [])\n    ):\n        return None\n'''
new = '''    all_probes = CONTROL_PROBES.get(int(case.get("task_number", 0)), ())\n    preferred_order = case.get("probe_operation_order")\n    if preferred_order:\n        by_operation = {item["operation_index"]: item for item in all_probes}\n        probes = tuple(by_operation[index] for index in preferred_order if index in by_operation)\n    else:\n        probes = all_probes\n\n    # Generic diagnostics still stop after a correct disambiguating probe.\n    # A task-context diagnostic may explicitly continue through a short list of\n    # operations that are all required by the student's failed task. This is\n    # not gap fishing: the list is fixed by the task family before any probe.\n    if not case.get("continue_after_correct_probe") and any(\n        item.get("kind") == "control_probe" and item.get("is_correct") is True\n        for item in case.get("evidence", [])\n    ):\n        return None\n'''
if old not in text:
    raise SystemExit('next_control_probe prelude not found')
text = text.replace(old, new, 1)
p.write_text(text, encoding='utf-8')

# 2) Route task-first errors to the operations that actually belong to the failed task.
p = Path('src/services/ege_exam_service.py')
text = p.read_text(encoding='utf-8')
old = '''    if not is_correct:\n        attempt.answers[task_number] = answer\n        attempt.results[task_number] = False\n        attempt.diagnostics[task_number] = open_diagnostic_case(\n            task_number=task_number,\n            student_answer=answer,\n            expected_answer=str(TUTOR_PILOT_TRANSFER_TASKS[task_number]["answer"]),\n            skill_map=load_skill_map(),\n        )\n    return is_correct\n'''
new = '''    if not is_correct:\n        attempt.answers[task_number] = answer\n        attempt.results[task_number] = False\n        case = open_diagnostic_case(\n            task_number=task_number,\n            student_answer=answer,\n            expected_answer=str(TUTOR_PILOT_TRANSFER_TASKS[task_number]["answer"]),\n            skill_map=load_skill_map(),\n        )\n        if task_number == 14:\n            # The transfer asks for hexadecimal conversion plus a property of\n            # the resulting digits. Check exactly those parts instead of an\n            # arbitrary first micro-skill, and allow the short fixed path to\n            # continue when one sub-skill is ruled out.\n            case["probe_operation_order"] = [1, 0, 2]\n            case["continue_after_correct_probe"] = True\n            case["diagnostic_context"] = "hex_conversion_even_digit_count"\n        elif task_number == 27:\n            # The small transfer already supplies the clusters; it tests only\n            # selection of the task-defined center, not cluster discovery.\n            case["probe_operation_order"] = [1]\n            case["diagnostic_context"] = "given_clusters_center_selection"\n        attempt.diagnostics[task_number] = case\n    return is_correct\n'''
if old not in text:
    raise SystemExit('record_tutor_pilot_transfer_answer block not found')
text = text.replace(old, new, 1)

old_file = '''    if not is_correct:\n        attempt.diagnostics[27] = open_diagnostic_case(\n            task_number=27,\n            student_answer=answer,\n            expected_answer=" ".join(map(str, expected)),\n            skill_map=load_skill_map(),\n        )\n    else:\n'''
new_file = '''    if not is_correct:\n        case = open_diagnostic_case(\n            task_number=27,\n            student_answer=answer,\n            expected_answer=" ".join(map(str, expected)),\n            skill_map=load_skill_map(),\n        )\n        # The real-file stage first needs to distinguish cluster separation\n        # from center selection. Do not misdiagnose a file error from an\n        # unrelated label-count/max-distance quiz. File-specific filtering and\n        # output-format diagnostics will be layered after these foundations.\n        case["probe_operation_order"] = [0, 1]\n        case["continue_after_correct_probe"] = True\n        case["diagnostic_context"] = stage\n        attempt.diagnostics[27] = case\n    else:\n'''
if old_file not in text:
    raise SystemExit('record_tutor_pilot_task27_file_answer block not found')
text = text.replace(old_file, new_file, 1)
p.write_text(text, encoding='utf-8')

# 3) Regression tests: task14 must not start with an unrelated remainder probe,
# and the small task27 transfer must diagnose center selection, not cluster count.
p = Path('tests/test_ege_tutor_pilot.py')
t = p.read_text(encoding='utf-8')
addition = '''\n\ndef test_task14_transfer_error_routes_to_relevant_fixed_diagnostic_path():\n    from src.services.ege_exam_service import next_attempt_diagnostic_probe\n    attempt = create_task_first_tutor_attempt()\n    assert record_tutor_pilot_transfer_answer(attempt, 14, "2") is False\n    case = attempt.diagnostics[14]\n    assert case["probe_operation_order"] == [1, 0, 2]\n    assert case["continue_after_correct_probe"] is True\n    probe = next_attempt_diagnostic_probe(attempt)\n    assert probe["task_number"] == 14\n    assert probe["operation_index"] == 1\n\n\ndef test_task27_small_transfer_error_diagnoses_center_not_cluster_count():\n    from src.services.ege_exam_service import next_attempt_diagnostic_probe\n    attempt = create_task_first_tutor_attempt()\n    assert record_tutor_pilot_transfer_answer(attempt, 27, "999") is False\n    case = attempt.diagnostics[27]\n    assert case["probe_operation_order"] == [1]\n    probe = next_attempt_diagnostic_probe(attempt)\n    assert probe["operation_index"] == 1\n\n\ndef test_task27_file_error_uses_only_file_foundation_diagnostics():\n    from src.services.ege_exam_service import next_attempt_diagnostic_probe, record_tutor_pilot_task27_file_answer\n    attempt = create_task_first_tutor_attempt()\n    assert record_tutor_pilot_task27_file_answer(attempt, "task27_file_a", "4545 85787") is False\n    case = attempt.diagnostics[27]\n    assert case["probe_operation_order"] == [0, 1]\n    assert case["continue_after_correct_probe"] is True\n    assert next_attempt_diagnostic_probe(attempt)["operation_index"] == 0\n'''
if 'test_task14_transfer_error_routes_to_relevant_fixed_diagnostic_path' not in t:
    t += addition
p.write_text(t, encoding='utf-8')

# 4) Protect the diagnostic primitive itself: in a fixed task-context path, a
# correct first probe moves to the next relevant operation rather than ending
# the whole case.
p = Path('tests/test_pilot_diagnostic_flow.py')
t = p.read_text(encoding='utf-8')
addition = '''\n\ndef test_context_diagnostic_can_continue_after_correct_probe_without_gap_fishing():\n    from src.ai_engine.diagnostics import open_diagnostic_case\n    from src.skills.skill_graph import load_skill_map\n    attempt = create_pilot_diagnostic_attempt()\n    case = open_diagnostic_case(14, "2", "3", load_skill_map())\n    case["probe_operation_order"] = [1, 0]\n    case["continue_after_correct_probe"] = True\n    attempt.diagnostics = {14: case}\n    first = next_attempt_diagnostic_probe(attempt)\n    assert first["operation_index"] == 1\n    bind_current_diagnostic_probe(attempt)\n    mark_current_diagnostic_probe_displayed(attempt)\n    # C=12 is even, so this correctly rules out digit-property confusion.\n    result = submit_diagnostic_answer(attempt, "да")\n    assert result["is_correct"] is True\n    second = next_attempt_diagnostic_probe(attempt)\n    assert second is not None\n    assert second["operation_index"] == 0\n'''
if 'test_context_diagnostic_can_continue_after_correct_probe_without_gap_fishing' not in t:
    t += addition
p.write_text(t, encoding='utf-8')
