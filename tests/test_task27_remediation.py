import json
from pathlib import Path
import pytest
from src.ai_engine.diagnostic_evidence_gate import answer_bound_control_probe
from src.ai_engine.diagnostics import apply_live_probe, next_control_probe, open_diagnostic_case
from src.learning_dna.engine import apply_confirmed_ege_diagnostics, confirm_ege_remediation_mastery
from src.services.ege_exam_service import ExamAttempt, TASK27_REMEDIATION, render_task27_remediation, start_task27_remediation, submit_task27_remediation_answer

def _attempt():
    skill_map=json.loads((Path(__file__).parents[1]/"src"/"skills"/"ege_informatics_2026.json").read_text(encoding="utf-8"))
    attempt=ExamAttempt(attempt_id="task27-remediation", current_task=28)
    case=open_diagnostic_case(27,"wrong","expected",skill_map)
    for answer in ("wrong","wrong-again"):
        probe=next_control_probe(case); case=apply_live_probe(case,probe); case["pending_probe"]["displayed"]=True
        case=answer_bound_control_probe(case,probe["probe_id"],answer,student_id=123,attempt_id=attempt.attempt_id)
    attempt.diagnostics[27]=case
    return attempt

def test_task27_full_learning_cycle_marks_atomic_skill():
    attempt=_attempt(); dna,_=apply_confirmed_ege_diagnostics(None,123,attempt); remediation=start_task27_remediation(attempt)
    assert remediation["skill_id"]=="programming.cluster_count_from_separation"
    assert "расстоя" in render_task27_remediation(attempt).lower()
    lesson=TASK27_REMEDIATION[remediation["skill_id"]]
    for stage in ("control","retest","verification"):
        result=submit_task27_remediation_answer(attempt,lesson[f"{stage}_answers"][0]); assert result["is_correct"] is True
    dna=confirm_ege_remediation_mastery(dna,27,attempt.attempt_id,attempt.remediation)
    skill=dna["skills"]["programming.cluster_count_from_separation"]
    assert skill["mastered"] is True
    assert [e["stage"] for e in skill["remediation_evidence"]]==["control","retest","verification"]

def test_task27_failed_verification_restarts_round():
    attempt=_attempt(); remediation=start_task27_remediation(attempt); lesson=TASK27_REMEDIATION[remediation["skill_id"]]
    submit_task27_remediation_answer(attempt,lesson["control_answers"][0]); submit_task27_remediation_answer(attempt,lesson["retest_answers"][0])
    result=submit_task27_remediation_answer(attempt,"wrong")
    assert result["is_correct"] is False and attempt.remediation["stage"]=="control" and attempt.remediation["learning_round"]==2

def test_task27_mastery_rejects_incomplete_evidence():
    attempt=_attempt(); dna,_=apply_confirmed_ege_diagnostics(None,123,attempt); remediation=start_task27_remediation(attempt); lesson=TASK27_REMEDIATION[remediation["skill_id"]]
    submit_task27_remediation_answer(attempt,lesson["control_answers"][0])
    with pytest.raises(ValueError): confirm_ege_remediation_mastery(dna,27,attempt.attempt_id,attempt.remediation)


def test_task27_center_remediation_uses_ege_wording():
    lesson = TASK27_REMEDIATION["programming.medoid_minimum"]
    assert "центр" in lesson["explanation"].lower()
    assert "среди исходных точек" in lesson["explanation"].lower()
    assert "медоид" not in lesson["control_prompt"].lower()
