from src.services.ege_exam_service import (
    ExamAttempt,
    create_pilot_diagnostic_attempt,
    render_summary,
    submit_answer,
    render_task14_remediation,
    start_task14_remediation,
    submit_task14_remediation_answer,
)
from src.ai_engine.diagnostics import answer_control_probe, next_control_probe, open_diagnostic_case
import json
from pathlib import Path
from src.ai_engine.ege_open_variant_2026 import OPEN_VARIANT_2026


def answer_text(task):
    return "\n".join(" ".join(row) for row in task.answer_rows)


def test_pilot_diagnostic_attempt_contains_only_selected_tasks():
    attempt = create_pilot_diagnostic_attempt()

    assert attempt.finished is True
    assert set(attempt.diagnostics) == {5, 14, 27}
    assert set(attempt.answers) == {5, 14, 27}
    assert all(result is False for result in attempt.results.values())


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


def _confirmed_task14_attempt():
    skill_map = json.loads(
        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
    )
    attempt = ExamAttempt(current_task=28)
    case = open_diagnostic_case(14, "wrong", "expected", skill_map)
    case = answer_control_probe(case, next_control_probe(case)["probe_id"], "wrong")
    case = answer_control_probe(case, next_control_probe(case)["probe_id"], "wrong")
    attempt.diagnostics[14] = case
    return attempt


def test_task14_remediation_survives_roundtrip_and_confirms_mastery():
    attempt = _confirmed_task14_attempt()
    remediation = start_task14_remediation(attempt)
    assert remediation["status"] == "remediating"
    assert "Контроль" in render_task14_remediation(attempt, include_lesson=True)

    wrong = submit_task14_remediation_answer(attempt, "999")
    assert wrong["status"] == "remediating"
    assert wrong["stage"] == "control"
    retry_text = render_task14_remediation(attempt)
    assert "Подсказка" in retry_text
    assert "Правило ещё раз" in retry_text

    control = submit_task14_remediation_answer(attempt, "20")
    assert control["stage"] == "retest"
    restored = ExamAttempt.from_dict(attempt.to_dict())
    assert restored.remediation["stage"] == "retest"

    retest = submit_task14_remediation_answer(restored, "2")
    assert retest["status"] == "retesting"
    assert retest["stage"] == "verification"
    assert "НЕЗАВИСИМАЯ ПРОВЕРКА" in render_task14_remediation(restored)

    verification = submit_task14_remediation_answer(restored, "21")
    assert verification["status"] == "mastered"
    assert verification["stage"] == "completed"


def test_failed_task14_verification_starts_a_fresh_learning_round():
    attempt = _confirmed_task14_attempt()
    start_task14_remediation(attempt)
    submit_task14_remediation_answer(attempt, "20")
    submit_task14_remediation_answer(attempt, "2")

    failed = submit_task14_remediation_answer(attempt, "999")

    assert failed["status"] == "remediating"
    assert failed["stage"] == "control"
    assert attempt.remediation["learning_round"] == 2
    assert "КОРОТКОЕ ОБУЧЕНИЕ" in render_task14_remediation(attempt)


def test_task14_remediation_restores_full_lesson_before_first_control_answer():
    attempt = _confirmed_task14_attempt()
    start_task14_remediation(attempt)

    restored = ExamAttempt.from_dict(attempt.to_dict())
    text = render_task14_remediation(restored)

    assert "КОРОТКОЕ ОБУЧЕНИЕ" in text
    assert "Правило:" in text
    assert "Разобранный пример:" in text


def test_task14_retest_wrong_answer_gets_transfer_hint():
    attempt = _confirmed_task14_attempt()
    start_task14_remediation(attempt)
    submit_task14_remediation_answer(attempt, "20")

    wrong = submit_task14_remediation_answer(attempt, "999")

    assert wrong["stage"] == "retest"
    assert "Почти получилось" in render_task14_remediation(attempt)
