

def test_ege_tasks_are_partitioned_by_solution_mode():
    from src.skills.skill_graph import tasks_by_solution_mode
    assert tasks_by_solution_mode("reasoning") == [1, 2, 4, 5, 6, 7, 8, 11, 12, 13, 14, 15, 16, 19, 20, 21, 23]
    assert tasks_by_solution_mode("application") == [3, 9, 10, 18, 22]
    assert tasks_by_solution_mode("programming") == [17, 24, 25, 26, 27]


def test_task27_is_programming_but_task5_and_14_are_reasoning():
    from src.skills.skill_graph import get_task_solution_mode
    assert get_task_solution_mode(27) == "programming"
    assert get_task_solution_mode(5) == "reasoning"
    assert get_task_solution_mode(14) == "reasoning"
