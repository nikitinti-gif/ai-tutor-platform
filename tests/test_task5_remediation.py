from src.ai_engine.diagnostics import apply_live_probe, next_control_probe, open_diagnostic_case
from src.ai_engine.diagnostic_evidence_gate import answer_bound_control_probe
from src.services.ege_exam_service import TASK5_REMEDIATION, ExamAttempt, render_task5_remediation, start_task5_remediation, submit_task5_remediation_answer
from src.skills.skill_graph import load_skill_map


def _confirmed_task5_attempt():
    attempt = ExamAttempt()
    case = open_diagnostic_case(5, "wrong", "expected", load_skill_map())
    for answer in ("wrong-1", "wrong-2"):
        probe = next_control_probe(case)
        case = apply_live_probe(case, probe)
        case["pending_probe"]["displayed"] = True
        case = answer_bound_control_probe(case, probe["probe_id"], answer, student_id=42, attempt_id=attempt.attempt_id)
    attempt.diagnostics[5] = case
    return attempt


def test_task5_confirmed_atomic_skill_is_taught_before_later_tasks():
    attempt = _confirmed_task5_attempt()
    remediation = start_task5_remediation(attempt)
    assert remediation["task_number"] == 5
    assert remediation["skill_id"] == "number_systems.decimal_binary_conversion"
    assert "КОРОТКОЕ ОБУЧЕНИЕ · №5" in render_task5_remediation(attempt, include_lesson=True)
    lesson = TASK5_REMEDIATION[remediation["skill_id"]]
    for stage in ("control", "retest", "verification"):
        assert attempt.remediation["stage"] == stage
        result = submit_task5_remediation_answer(attempt, lesson[f"{stage}_answers"][0])
    assert result["status"] == "mastered"
    assert [item["stage"] for item in attempt.remediation["stage_history"]] == ["control", "retest", "verification"]
