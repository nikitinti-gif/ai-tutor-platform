from src.services.ege_exam_service import (
    TUTOR_PILOT_TASKS,
    create_task_first_tutor_attempt,
    record_tutor_pilot_answer,
    render_tutor_pilot_task,
    render_tutor_pilot_transfer_task,
    record_tutor_pilot_transfer_answer,
    record_tutor_pilot_task27_file_answer,
    render_tutor_pilot_task27_file_stage,
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


def test_task27_uses_current_ege_center_definition_not_centroid_average():
    rendered = render_tutor_pilot_task(27)
    assert "одна из исходных точек" in rendered
    assert "сумма расстояний" in rendered
    assert "среднее арифметическое координат" not in rendered
    assert "Связь с реальным №27" in rendered
    assert "читаются из файлов" in rendered


def test_task27_real_file_stage_uses_official_data_and_python_reference_solver():
    attempt = create_task_first_tutor_attempt()
    rendered_a = render_tutor_pilot_task27_file_stage("task27_file_a")
    rendered_b = render_tutor_pilot_task27_file_stage("task27_file_b")
    assert "настоящий файл" in rendered_a.lower()
    assert "красных гигантов" in rendered_a
    assert "оранжевых гигантов" in rendered_b
    assert "жёлтыми карликами" in rendered_b
    assert record_tutor_pilot_task27_file_answer(attempt, "task27_file_a", "44694 69754") is True
    assert 27 not in attempt.diagnostics
    assert record_tutor_pilot_task27_file_answer(attempt, "task27_file_b", "138716 34029") is True
    assert 27 not in attempt.diagnostics


def test_task27_real_file_error_opens_diagnostic_case():
    attempt = create_task_first_tutor_attempt()
    assert record_tutor_pilot_task27_file_answer(attempt, "task27_file_a", "1 2") is False
    assert 27 in attempt.diagnostics
    assert attempt.diagnostics[27]["expected_answer"] == "44694 69754"


def test_task14_transfer_error_routes_to_relevant_fixed_diagnostic_path():
    from src.services.ege_exam_service import next_attempt_diagnostic_probe
    attempt = create_task_first_tutor_attempt()
    assert record_tutor_pilot_transfer_answer(attempt, 14, "2") is False
    case = attempt.diagnostics[14]
    assert case["probe_operation_order"] == [1, 0, 2]
    assert case["continue_after_correct_probe"] is True
    probe = next_attempt_diagnostic_probe(attempt)
    assert probe["task_number"] == 14
    assert probe["operation_index"] == 1


def test_task27_small_transfer_error_diagnoses_center_not_cluster_count():
    from src.services.ege_exam_service import next_attempt_diagnostic_probe
    attempt = create_task_first_tutor_attempt()
    assert record_tutor_pilot_transfer_answer(attempt, 27, "999") is False
    case = attempt.diagnostics[27]
    assert case["probe_operation_order"] == [1]
    probe = next_attempt_diagnostic_probe(attempt)
    assert probe["operation_index"] == 1


def test_task27_file_error_uses_only_file_foundation_diagnostics():
    from src.services.ege_exam_service import next_attempt_diagnostic_probe, record_tutor_pilot_task27_file_answer
    attempt = create_task_first_tutor_attempt()
    assert record_tutor_pilot_task27_file_answer(attempt, "task27_file_a", "4545 85787") is False
    case = attempt.diagnostics[27]
    assert case["probe_operation_order"] == [0, 1]
    assert case["continue_after_correct_probe"] is True
    assert next_attempt_diagnostic_probe(attempt)["operation_index"] == 0


def test_tutor_pilot_architecture_keeps_programming_separate_from_reasoning():
    from src.skills.skill_graph import get_task_solution_mode
    assert [get_task_solution_mode(n) for n in (5, 14)] == ["reasoning", "reasoning"]
    assert get_task_solution_mode(27) == "programming"
