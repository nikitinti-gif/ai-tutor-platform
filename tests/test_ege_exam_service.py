from src.services.ege_exam_service import ExamAttempt, render_summary, submit_answer
from src.ai_engine.ege_open_variant_2026 import OPEN_VARIANT_2026


def answer_text(task):
    return "\n".join(" ".join(row) for row in task.answer_rows)


def test_complete_all_27_with_official_answers():
    attempt = ExamAttempt()
    for number in range(1, 28):
        result = submit_answer(attempt, answer_text(OPEN_VARIANT_2026[number]))
        assert result.is_correct
    assert attempt.finished
    assert attempt.correct_count == 27
    assert "27 из 27" in render_summary(attempt)


def test_wrong_answer_is_saved_and_flow_continues():
    attempt = ExamAttempt()
    result = submit_answer(attempt, "wrong")
    assert not result.is_correct
    assert attempt.current_task == 2
    assert attempt.results[1] is False
    assert attempt.diagnostics[1]["status"] == "needs_evidence"
    assert attempt.diagnostics[1]["failed_step"] is None


def test_roundtrip_state_dict():
    attempt = ExamAttempt()
    submit_answer(attempt, "9")
    restored = ExamAttempt.from_dict(attempt.to_dict())
    assert restored.current_task == 2
    assert restored.results == {1: True}
    assert restored.diagnostics == {}


def test_diagnostic_case_survives_state_roundtrip():
    attempt = ExamAttempt()
    submit_answer(attempt, "wrong")
    restored = ExamAttempt.from_dict(attempt.to_dict())
    assert restored.diagnostics[1]["student_answer"] == "wrong"
    assert restored.diagnostics[1]["status"] == "needs_evidence"
