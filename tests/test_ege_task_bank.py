from src.services.ege_task_bank import (
    choose_task14,
    get_task,
    render_task,
    task14_bank,
    validate_answer,
)


def test_task14_bank_has_curated_2026_tasks_with_provenance():
    tasks = task14_bank()
    assert len(tasks) >= 3
    assert all(task.task_number == 14 for task in tasks)
    assert all(task.source_problem_id for task in tasks)
    assert all(task.source_url.startswith("https://inf-ege.sdamgia.ru/") for task in tasks)
    assert all(task.family_id for task in tasks)
    assert all(task.skill_ids for task in tasks)


def test_task_bank_answers_are_locally_validated():
    expected = {
        "reshuege-89751": "1013",
        "reshuege-92256": "71",
        "reshuege-92258": "625",
    }
    for task_id, answer in expected.items():
        task = get_task(task_id)
        assert task.canonical_answer == answer
        assert validate_answer(task_id, answer) is True
        assert validate_answer(task_id, "definitely-wrong") is False


def test_selector_avoids_repeating_already_used_task():
    first = choose_task14()
    second = choose_task14(exclude_ids={first.task_id})
    assert second.task_id != first.task_id


def test_selector_can_choose_same_family_as_failed_task():
    task = choose_task14(family_id="large_power_digit_property")
    assert task.task_id == "reshuege-89751"


def test_student_render_has_attribution_but_not_site_solution():
    text = render_task(get_task("reshuege-92256"))
    assert "Источник: РЕШУ ЕГЭ" in text
    assert "№92256" in text
    assert "Ответ проверяет Python локально" in text
    assert "71" not in text
