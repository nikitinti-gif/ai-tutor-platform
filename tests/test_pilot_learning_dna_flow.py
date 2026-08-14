from src.ai_engine.diagnostics import CONTROL_PROBES, apply_live_probe
from src.learning_dna.engine import apply_confirmed_ege_diagnostics
from src.services.ege_exam_service import (
    create_pilot_diagnostic_attempt,
    next_attempt_diagnostic_probe,
    submit_diagnostic_answer,
)


def _confirm_first_gap_for_current_task(attempt):
    probe = next_attempt_diagnostic_probe(attempt)
    assert probe is not None
    task_number = probe["task_number"]

    attempt.diagnostics[task_number] = apply_live_probe(attempt.diagnostics[task_number], probe)
    attempt.diagnostics[task_number]["pending_probe"]["displayed"] = True
    first = submit_diagnostic_answer(attempt, "definitely-wrong")
    assert first["task_number"] == task_number
    assert first["status"] == "probable"

    transfer = next_attempt_diagnostic_probe(attempt)
    assert transfer is not None
    assert transfer["task_number"] == task_number
    assert transfer["probe_role"] == "transfer"

    attempt.diagnostics[task_number] = apply_live_probe(attempt.diagnostics[task_number], transfer)
    attempt.diagnostics[task_number]["pending_probe"]["displayed"] = True
    second = submit_diagnostic_answer(attempt, "still-wrong")
    assert second["task_number"] == task_number
    assert second["status"] == "confirmed"
    return task_number


def test_confirmed_pilot_diagnostics_build_learning_dna_plan_and_focus():
    student_id = 424242
    attempt = create_pilot_diagnostic_attempt()

    confirmed_tasks = [
        _confirm_first_gap_for_current_task(attempt)
        for _ in range(3)
    ]
    assert confirmed_tasks == [5, 14, 27]
    assert next_attempt_diagnostic_probe(attempt) is None

    dna, result = apply_confirmed_ege_diagnostics(None, student_id, attempt)

    assert result["applied_count"] == 3
    assert result["confirmed_count"] == 3
    assert result["plan_size"] == 3
    assert len(dna["processed_evidence_ids"]) == 3

    plan = dna["trajectory"]["individual_plan"]
    assert [item["task_number"] for item in plan] == [5, 14, 27]
    assert all(item["evidence_status"] == "confirmed" for item in plan)
    assert all(item["confidence"] == 0.95 for item in plan)
    assert all(item["failed_step"] for item in plan)
    assert all(item["action"] for item in plan)

    for item in plan:
        case = attempt.diagnostics[item["task_number"]]
        failed = [
            evidence for evidence in case["evidence"]
            if evidence.get("kind") == "control_probe"
            and evidence.get("evidence_valid") is True
            and evidence.get("validator_result") is False
        ]
        assert failed
        assert item["skill_id"] == failed[-1]["skill_id"]
        assert item["skill_id"] in dna["skills"]
        assert dna["skills"][item["skill_id"]]["mistakes"] >= 1

    assert dna["trajectory"]["next_focus"] == plan[0]["failed_step"]
    assert dna["trajectory"]["next_focus_skill_id"] == plan[0]["skill_id"]
    assert result["next_focus"] == plan[0]["failed_step"]


def test_learning_dna_write_is_idempotent_for_same_exam_attempt():
    student_id = 424242
    attempt = create_pilot_diagnostic_attempt()
    _confirm_first_gap_for_current_task(attempt)

    dna, first = apply_confirmed_ege_diagnostics(None, student_id, attempt)
    evidence_ids = list(dna["processed_evidence_ids"])
    signal_count = len(dna.get("signals", []))

    dna, second = apply_confirmed_ege_diagnostics(dna, student_id, attempt)

    assert first["applied_count"] == 1
    assert second["applied_count"] == 0
    assert dna["processed_evidence_ids"] == evidence_ids
    assert len(dna.get("signals", [])) == signal_count
    assert second["plan_size"] == 1


def test_unconfirmed_probe_does_not_enter_learning_dna():
    student_id = 424242
    attempt = create_pilot_diagnostic_attempt()

    probe = next_attempt_diagnostic_probe(attempt)
    assert probe is not None
    canonical_probe = next(
        item
        for item in CONTROL_PROBES[probe["task_number"]]
        if item["id"] == probe["base_probe_id"]
    )
    correct_answer = canonical_probe["expected_answers"][0]
    attempt.diagnostics[probe["task_number"]] = apply_live_probe(
        attempt.diagnostics[probe["task_number"]], probe
    )
    attempt.diagnostics[probe["task_number"]]["pending_probe"]["displayed"] = True
    result = submit_diagnostic_answer(attempt, correct_answer)
    assert result["is_correct"] is True
    assert result["status"] == "needs_evidence"

    dna, write_result = apply_confirmed_ege_diagnostics(None, student_id, attempt)

    assert write_result["applied_count"] == 0
    assert write_result["confirmed_count"] == 0
    assert write_result["plan_size"] == 0
    assert dna["processed_evidence_ids"] == []
    assert dna["trajectory"]["individual_plan"] == []
    assert dna["trajectory"]["next_focus"] is None
