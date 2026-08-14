from pathlib import Path

service = Path('src/services/ege_exam_service.py')
text = service.read_text(encoding='utf-8')
old = '''            generated = build_live_probe(case, {
                "id": probe["base_probe_id"],
                "operation_index": probe["operation_index"],
            }, raw, previous_prompts=context["previous_prompts"] + rejected_prompts, values=values, variant=str(probe_data["variant"]))
            break
'''
new = '''            generated = build_live_probe(case, {
                "id": probe["base_probe_id"],
                "operation_index": probe["operation_index"],
            }, raw, previous_prompts=context["previous_prompts"] + rejected_prompts, values=values, variant=str(probe_data["variant"]))
            # Keep the Python-selected evidence role. The strict evidence gate
            # deliberately defaults a missing role to discrimination; losing
            # this field made every AI-worded retry look like a first probe.
            generated["probe_role"] = probe["probe_role"]
            generated["tested_step"] = probe["tested_step"]
            break
'''
if old not in text:
    raise SystemExit('AI generated probe anchor missing')
service.write_text(text.replace(old, new, 1), encoding='utf-8')

tests = Path('tests/test_ege_diagnostics.py')
text = tests.read_text(encoding='utf-8')
old_sample = '(14, 2): ("Алгоритм получил {count} остатков, после чего осталось ненулевое частное. Сколько разрядов будет в записи?", [5]),'
new_sample = '(14, 2): ("Алгоритм получил {remainder_count} остатков, после чего осталось ненулевое частное. Сколько разрядов будет в записи?", [5]),'
if old_sample in text:
    text = text.replace(old_sample, new_sample, 1)
tests.write_text(text, encoding='utf-8')

quality = Path('tests/test_probe_quality_gate.py')
text = quality.read_text(encoding='utf-8')
addition = '''\n\ndef test_task14_most_significant_digit_rejects_semantically_wrong_total_count():
    from src.ai_engine.diagnostics import CONTROL_PROBES, open_diagnostic_case
    from src.ai_engine.live_diagnostic_probes import build_live_probe
    from src.skills.skill_graph import load_skill_map

    case = open_diagnostic_case(14, "wrong", "expected", load_skill_map())
    raw = json.dumps({"prompt_template": "Если общее количество всех этих значимых элементов равно {remainder_count}, сколько всего разрядов будет в записи?"}, ensure_ascii=False)
    with pytest.raises(ValueError):
        build_live_probe(case, CONTROL_PROBES[14][2], raw, values=[4])


def test_task14_most_significant_digit_accepts_explicit_remainder_count():
    from src.ai_engine.diagnostics import CONTROL_PROBES, open_diagnostic_case
    from src.ai_engine.live_diagnostic_probes import build_live_probe
    from src.skills.skill_graph import load_skill_map

    case = open_diagnostic_case(14, "wrong", "expected", load_skill_map())
    raw = json.dumps({"prompt_template": "После делений получено {remainder_count} остатков и осталось последнее ненулевое частное. Сколько цифр будет в итоговой записи?"}, ensure_ascii=False)
    probe = build_live_probe(case, CONTROL_PROBES[14][2], raw, values=[4])
    assert probe["expected_answers"] == ("5",)
'''
if 'test_task14_most_significant_digit_rejects_semantically_wrong_total_count' not in text:
    text += addition
quality.write_text(text, encoding='utf-8')

evidence_test = Path('tests/test_live_ai_probe_evidence_roles.py')
evidence_test.write_text('''from src.ai_engine.diagnostics import apply_live_probe, next_control_probe, open_diagnostic_case
from src.ai_engine.diagnostic_evidence_gate import answer_bound_control_probe
from src.services.ege_exam_service import ExamAttempt
from src.skills.skill_graph import load_skill_map


def _show(case, generated):
    generated = dict(generated)
    generated["displayed"] = True
    return apply_live_probe(case, generated)


def test_two_ai_worded_wrong_probes_confirm_same_task14_gap():
    attempt = ExamAttempt()
    case = open_diagnostic_case(14, "wrong", "expected", load_skill_map())

    first = next_control_probe(case)
    first_generated = {
        "probe_id": first["probe_id"] + ":ai1",
        "base_probe_id": first["base_probe_id"],
        "operation_index": first["operation_index"],
        "prompt": "Какой остаток?",
        "expected_answers": ("1",),
        "source": "ai_wording_parameters_python_solver",
        "probe_role": first["probe_role"],
        "tested_step": first["tested_step"],
    }
    case = _show(case, first_generated)
    case = answer_bound_control_probe(case, first_generated["probe_id"], "999", student_id=42, attempt_id=attempt.attempt_id)
    assert case["status"] == "probable"
    assert case["evidence"][-1]["probe_role"] == "discrimination"

    second = next_control_probe(case)
    assert second["probe_role"] == "transfer"
    second_generated = {
        "probe_id": second["probe_id"] + ":ai2",
        "base_probe_id": second["base_probe_id"],
        "operation_index": second["operation_index"],
        "prompt": "Какой остаток на новых данных?",
        "expected_answers": ("2",),
        "source": "ai_wording_parameters_python_solver",
        "probe_role": second["probe_role"],
        "tested_step": second["tested_step"],
    }
    case = _show(case, second_generated)
    case = answer_bound_control_probe(case, second_generated["probe_id"], "999", student_id=42, attempt_id=attempt.attempt_id)

    assert case["status"] == "confirmed"
    assert case["evidence"][-1]["probe_role"] == "transfer"
    assert case["gap_hypotheses"][0]["status"] == "confirmed"
''', encoding='utf-8')
