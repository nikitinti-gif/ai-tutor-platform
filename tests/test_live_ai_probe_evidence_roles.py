from src.ai_engine.diagnostics import apply_live_probe, next_control_probe, open_diagnostic_case
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
