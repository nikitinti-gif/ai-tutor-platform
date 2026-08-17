from src.services.ege_learning_path import (
    TASK14_LEVELS,
    LearningPath,
    build_learning_path,
    current_step,
    render_current_step,
    submit_answer,
)


def test_task14_path_runs_from_foundation_to_exam_level():
    path = build_learning_path(14)
    assert path.solution_mode == "reasoning"
    assert current_step(path)["id"] == "digit_value"
    assert TASK14_LEVELS[-1]["difficulty"] == "exam"
    answers = [level["answers"][0] for level in TASK14_LEVELS]
    for answer in answers:
        result = submit_answer(path, str(answer))
        assert result["is_correct"] is True
    assert path.status == "mastered"
    assert current_step(path) is None
    assert len(path.history) == len(TASK14_LEVELS)
    assert path.history[-1]["difficulty"] == "exam"


def test_wrong_answer_does_not_create_fake_weakness_or_advance():
    path = build_learning_path(14)
    first = current_step(path)
    result = submit_answer(path, "999")
    assert result["is_correct"] is False
    assert result["needs_teaching"] is False
    assert current_step(path)["id"] == first["id"]
    result = submit_answer(path, "999")
    assert result["needs_teaching"] is True
    assert path.status == "learning"
    assert path.current_index == 0


def test_path_state_survives_serialization():
    path = build_learning_path(14)
    submit_answer(path, TASK14_LEVELS[0]["answers"][0])
    restored = LearningPath.from_dict(path.to_dict())
    assert restored.task_number == 14
    assert restored.current_index == 1
    assert restored.history == path.history
    assert current_step(restored)["id"] == "small_conversion"


def test_render_makes_progression_visible_to_student():
    path = build_learning_path(14)
    text = render_current_step(path)
    assert "ПУТЬ К №14" in text
    assert "ШАГ 1/7" in text
    assert "Значение буквенной цифры" in text
    assert "Отправь только ответ" in text


def test_task14_final_step_is_real_open_variant_not_microprobe():
    final = TASK14_LEVELS[-1]
    assert "5·1296^2021" in final["prompt"]
    assert final["answers"] == ("1013",)
    assert final["difficulty"] == "exam"


def test_learning_path_rejects_programming_task_until_programming_tutor_exists():
    try:
        build_learning_path(27)
    except ValueError as error:
        assert "only for task 14" in str(error)
    else:
        raise AssertionError("task 27 must not enter the reasoning Learning Path")



def test_exam_attempt_persists_learning_path_state():
    from src.services.ege_exam_service import ExamAttempt
    path = build_learning_path(14)
    submit_answer(path, TASK14_LEVELS[0]["answers"][0])
    attempt = ExamAttempt()
    attempt.results[14] = False
    attempt.learning_path = path.to_dict()
    restored = ExamAttempt.from_dict(attempt.to_dict())
    restored_path = LearningPath.from_dict(restored.learning_path)
    assert restored.results[14] is False
    assert restored_path.current_index == 1
    assert current_step(restored_path)["id"] == "small_conversion"
