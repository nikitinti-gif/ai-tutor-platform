from src.ai_engine.diagnostics import CONTROL_PROBES
from src.learning_dna.engine import (
    apply_confirmed_ege_diagnostics,
    confirm_ege_remediation_mastery,
    set_ege_remediation_status,
)
from src.services.ege_exam_service import (
    TASK14_REMEDIATION,
    TASK27_REMEDIATION,
    bind_current_diagnostic_probe,
    create_pilot_diagnostic_attempt,
    mark_current_diagnostic_probe_displayed,
    next_attempt_diagnostic_probe,
    start_task14_remediation,
    start_task27_remediation,
    submit_diagnostic_answer,
    submit_task14_remediation_answer,
    submit_task27_remediation_answer,
)


def _canonical_probe_answer(task: int, base_probe_id: str) -> str:
    probe = next(item for item in CONTROL_PROBES[task] if item["id"] == base_probe_id)
    return str(probe["expected_answers"][0])


def _finish_diagnostics(attempt, student_id: int = 4242):
    """Task 5 is disproved; first atomic skills of 14 and 27 are confirmed."""
    while True:
        probe = next_attempt_diagnostic_probe(attempt)
        if probe is None:
            return

        probe = bind_current_diagnostic_probe(attempt)
        assert probe is not None
        task = probe["task_number"]
        expected = _canonical_probe_answer(task, probe["base_probe_id"])

        if task == 5:
            # Every isolated step is answered correctly, so the original error
            # must not become a fabricated weakness in Learning DNA.
            answer = expected
        elif task in {14, 27} and int(probe["operation_index"]) == 0:
            # Two independent negative evidence items confirm one atomic skill.
            answer = "definitely-wrong"
        else:
            # These branches should never be reached after operation 0 is confirmed.
            answer = expected

        mark_current_diagnostic_probe_displayed(attempt)
        submit_diagnostic_answer(attempt, answer, student_id=student_id)


def _complete_task14_learning(attempt, dna):
    remediation = start_task14_remediation(attempt)
    assert remediation is not None
    assert remediation["task_number"] == 14
    dna = set_ege_remediation_status(dna, 14, "remediating")
    lesson = TASK14_REMEDIATION[remediation["gap_id"]]

    for stage in ("control", "retest", "verification"):
        assert attempt.remediation["stage"] == stage
        result = submit_task14_remediation_answer(
            attempt, str(lesson[f"{stage}_answers"][0])
        )
        assert result["is_correct"] is True

    assert attempt.remediation["status"] == "mastered"
    dna = confirm_ege_remediation_mastery(
        dna, 14, attempt.attempt_id, remediation=attempt.remediation
    )
    return dna


def _complete_task27_learning(attempt, dna):
    # The real Telegram flow clears the completed remediation before starting
    # the next confirmed gap from the individual plan.
    attempt.remediation = {}
    remediation = start_task27_remediation(attempt)
    assert remediation is not None
    assert remediation["task_number"] == 27
    dna = set_ege_remediation_status(dna, 27, "remediating")
    lesson = TASK27_REMEDIATION[remediation["skill_id"]]

    for stage in ("control", "retest", "verification"):
        assert attempt.remediation["stage"] == stage
        result = submit_task27_remediation_answer(
            attempt, str(lesson[f"{stage}_answers"][0])
        )
        assert result["is_correct"] is True

    assert attempt.remediation["status"] == "mastered"
    dna = confirm_ege_remediation_mastery(
        dna, 27, attempt.attempt_id, remediation=attempt.remediation
    )
    return dna


def test_pilot_5_14_27_full_student_loop_reaches_verified_learning_dna():
    """One regression protects diagnosis -> teaching -> mastery end to end."""
    student_id = 4242
    attempt = create_pilot_diagnostic_attempt()

    _finish_diagnostics(attempt, student_id=student_id)

    assert attempt.diagnostics[5]["status"] != "confirmed"
    assert attempt.diagnostics[14]["status"] == "confirmed"
    assert attempt.diagnostics[27]["status"] == "confirmed"

    dna, write = apply_confirmed_ege_diagnostics(None, student_id, attempt)
    plan = dna["trajectory"]["individual_plan"]

    assert write["applied_count"] == 2
    assert [item["task_number"] for item in plan] == [14, 27]
    assert plan[0]["skill_id"] == "number_systems.calculate_remainder"
    assert plan[1]["skill_id"] == "programming.cluster_count_from_separation"
    assert not any(item["task_number"] == 5 for item in plan)

    dna = _complete_task14_learning(attempt, dna)
    assert dna["skills"]["number_systems.calculate_remainder"]["mastered"] is True
    assert len(
        dna["skills"]["number_systems.calculate_remainder"]["remediation_evidence"]
    ) == 3

    dna = _complete_task27_learning(attempt, dna)
    assert dna["skills"]["programming.cluster_count_from_separation"]["mastered"] is True
    assert len(
        dna["skills"]["programming.cluster_count_from_separation"]["remediation_evidence"]
    ) == 3

    # Both originally confirmed weaknesses have now been taught and independently
    # verified. The next focus must no longer point at either mastered skill.
    next_focus_skill = dna["trajectory"].get("next_focus_skill_id")
    assert next_focus_skill not in {
        "number_systems.calculate_remainder",
        "programming.cluster_count_from_separation",
    }
