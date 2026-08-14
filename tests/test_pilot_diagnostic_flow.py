from src.services.ege_exam_service import (
    bind_current_diagnostic_probe,
    mark_current_diagnostic_probe_displayed,
    create_pilot_diagnostic_attempt,
    next_attempt_diagnostic_probe,
    submit_diagnostic_answer,
)


def test_pilot_correct_probe_rejects_first_task5_hypothesis_and_moves_on():
    attempt = create_pilot_diagnostic_attempt()

    first = next_attempt_diagnostic_probe(attempt)
    assert first is not None
    assert first["task_number"] == 5
    assert first["operation_index"] == 0

    bind_current_diagnostic_probe(attempt)
    mark_current_diagnostic_probe_displayed(attempt)
    result = submit_diagnostic_answer(attempt, "10011")
    assert result["task_number"] == 5
    assert result["is_correct"] is True
    assert result["status"] == "needs_evidence"

    next_probe = next_attempt_diagnostic_probe(attempt)
    assert next_probe is not None
    assert next_probe["task_number"] == 5
    assert next_probe["operation_index"] == 1


def test_pilot_can_confirm_one_real_gap_per_task_and_finish_5_14_27_flow():
    attempt = create_pilot_diagnostic_attempt()

    for expected_task in (5, 14, 27):
        discrimination = next_attempt_diagnostic_probe(attempt)
        assert discrimination is not None
        assert discrimination["task_number"] == expected_task
        assert discrimination["probe_role"] == "discrimination"

        bind_current_diagnostic_probe(attempt)
        mark_current_diagnostic_probe_displayed(attempt)
        first_result = submit_diagnostic_answer(attempt, "definitely-wrong")
        assert first_result["task_number"] == expected_task
        assert first_result["is_correct"] is False
        assert first_result["status"] == "probable"

        transfer = next_attempt_diagnostic_probe(attempt)
        assert transfer is not None
        assert transfer["task_number"] == expected_task
        assert transfer["probe_role"] == "transfer"
        assert transfer["base_probe_id"] == discrimination["base_probe_id"]

        bind_current_diagnostic_probe(attempt)
        mark_current_diagnostic_probe_displayed(attempt)
        second_result = submit_diagnostic_answer(attempt, "still-wrong")
        assert second_result["task_number"] == expected_task
        assert second_result["is_correct"] is False
        assert second_result["status"] == "confirmed"
        assert attempt.diagnostics[expected_task]["confidence"] == 0.95

    assert next_attempt_diagnostic_probe(attempt) is None
    assert all(
        attempt.diagnostics[task_number]["status"] == "confirmed"
        for task_number in (5, 14, 27)
    )


def test_submit_rejects_answer_when_probe_was_not_shown():
    import pytest
    attempt = create_pilot_diagnostic_attempt()
    with pytest.raises(ValueError, match="показан|привязан"):
        submit_diagnostic_answer(attempt, "10011")


def test_prepared_probe_cannot_be_answered_until_display_is_acknowledged():
    import pytest
    attempt = create_pilot_diagnostic_attempt()
    bind_current_diagnostic_probe(attempt)
    with pytest.raises(ValueError, match="показ|подтвержд"):
        submit_diagnostic_answer(attempt, "10011")
    mark_current_diagnostic_probe_displayed(attempt)
    assert submit_diagnostic_answer(attempt, "10011")["is_correct"] is True
