from src.services.ege_exam_service import (
    TUTOR_PILOT_TASKS,
    create_task_first_tutor_attempt,
    record_tutor_pilot_answer,
    render_tutor_pilot_task,
    render_tutor_pilot_transfer_task,
    record_tutor_pilot_transfer_answer,
)


def test_tutor_pilot_starts_without_fake_diagnostic_cases():
    attempt = create_task_first_tutor_attempt()
    assert attempt.diagnostics == {}
    assert attempt.results == {}


def test_tutor_pilot_opens_case_only_after_real_error():
    attempt = create_task_first_tutor_attempt()
    assert record_tutor_pilot_answer(attempt, 5, TUTOR_PILOT_TASKS[5]["answer"]) is True
    assert 5 not in attempt.diagnostics
    assert record_tutor_pilot_answer(attempt, 14, "999") is False
    assert 14 in attempt.diagnostics
    assert attempt.diagnostics[14]["student_answer"] == "999"
    assert attempt.diagnostics[14]["expected_answer"] == TUTOR_PILOT_TASKS[14]["answer"]


def test_tutor_pilot_tasks_are_student_facing_not_engine_audit():
    for task_number in (5, 14, 27):
        rendered = render_tutor_pilot_task(task_number)
        assert "Гипотеза:" not in rendered
        assert "Почему эта проба подходит" not in rendered
        assert "FALLBACK_PROBE" not in rendered
        assert "TRAIN" not in rendered
        assert "Отправь только итоговый ответ" in rendered


def test_tutor_pilot_canonical_answers():
    attempt = create_task_first_tutor_attempt()
    assert record_tutor_pilot_answer(attempt, 5, "19") is True
    assert record_tutor_pilot_answer(attempt, 14, "1") is True
    assert record_tutor_pilot_answer(attempt, 27, "24") is True
    assert attempt.diagnostics == {}


def test_tutor_pilot_scaffolds_before_exam_style():
    rendered = render_tutor_pilot_task(5)
    assert "Что здесь нужно понять" in rendered
    assert "Разобранный пример" in rendered
    assert "Теперь попробуй сам" in rendered
    assert "1) запиши N в двоичной системе" in rendered
    assert "получившуюся двоичную запись переведи обратно" in rendered
    assert "Полученная запись задаёт число R" not in rendered


def test_each_tutor_task_has_teacher_scaffolding():
    for task_number in (5, 14, 27):
        task = TUTOR_PILOT_TASKS[task_number]
        assert task["teacher_intro"]
        assert task["worked_example"]
        rendered = render_tutor_pilot_task(task_number)
        assert task["worked_example"] in rendered
        assert "Отправь только итоговый ответ" in rendered


def test_supported_success_requires_independent_transfer_before_mastery_signal():
    attempt = create_task_first_tutor_attempt()
    assert record_tutor_pilot_answer(attempt, 5, TUTOR_PILOT_TASKS[5]["answer"]) is True
    assert 5 not in attempt.diagnostics
    assert record_tutor_pilot_transfer_answer(attempt, 5, "999") is False
    assert 5 in attempt.diagnostics


def test_transfer_task_removes_teacher_scaffolding():
    rendered = render_tutor_pilot_transfer_task(5)
    assert "БЕЗ ПОДСКАЗКИ" in rendered
    assert "Разобранный пример" not in rendered
    assert "Что здесь нужно понять" not in rendered
    assert "N = 13" not in rendered
