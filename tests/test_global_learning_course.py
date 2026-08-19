import pytest

from src.learning_dna.engine import confirm_global_skill_mastery
from src.learning_dna.profile import create_default_learning_dna
from src.services.ege_learning_path import build_learning_path, current_step, submit_answer
from src.services.learning_course import MAX_RETRIES, MODULE_STEPS, build_course
from src.services.student_dashboard_service import build_student_dashboard


def test_course_deduplicates_shared_skill_and_keeps_all_exam_contexts():
    plan = [
        {"task_number": 5, "skill_id": "number_systems.base_conversion"},
        {"task_number": 12, "skill_id": "number_systems.base_conversion"},
        {"task_number": 14, "skill_id": "number_systems.base_conversion"},
    ]
    course = build_course(plan)
    assert len(course) == 1
    assert course[0].skill_id == "number_systems.base_conversion"
    assert {5, 8, 12, 13, 14}.issubset(course[0].related_exam_tasks)


def test_every_generic_module_has_deterministic_full_ladder():
    for skill_id, steps in MODULE_STEPS.items():
        assert tuple(step["difficulty"] for step in steps) == (
            "foundation", "basic", "intermediate", "transfer", "exam", "exam_transfer"
        )
        from src.skills.skill_graph import get_skill
        path = build_learning_path(get_skill(skill_id)["exam_tasks"][0], skill_id=skill_id)
        for step in steps:
            assert submit_answer(path, step["answers"][0])["is_correct"]
        assert path.status == "mastered"


def test_retry_policy_falls_back_instead_of_looping_forever():
    path = build_learning_path(8, skill_id="number_systems.base_conversion")
    submit_answer(path, current_step(path)["answers"][0])
    assert path.current_index == 1
    result = None
    for _ in range(MAX_RETRIES):
        result = submit_answer(path, "wrong")
    assert result["retry_limit_reached"] is True
    assert path.current_index == 0
    assert path.attempts_on_step == 0


def test_global_mastery_requires_complete_evidence_and_updates_one_dashboard_node():
    path = build_learning_path(8, skill_id="number_systems.base_conversion")
    with pytest.raises(ValueError):
        confirm_global_skill_mastery(create_default_learning_dna(1), path.skill_id, path.to_dict())
    for step in MODULE_STEPS[path.skill_id]:
        submit_answer(path, step["answers"][0])
    dna = create_default_learning_dna(1)
    dna["trajectory"]["individual_plan"] = [
        {"task_number": n, "skill_id": path.skill_id} for n in (5, 12, 14)
    ]
    updated = confirm_global_skill_mastery(dna, path.skill_id, path.to_dict())
    view = build_student_dashboard(updated)
    nodes = [node for node in view["nodes"] if node["skill_id"] == path.skill_id]
    assert len(nodes) == 1
    assert nodes[0]["status"] == "mastered"
    assert {5, 8, 12, 13, 14}.issubset(nodes[0]["exam_tasks"])


def test_deterministic_student_personas_receive_distinct_deduplicated_courses():
    personas = {
        "strong": [],
        "number_systems": [
            {"task_number": n, "skill_id": "number_systems.base_conversion"}
            for n in (5, 8, 12, 13, 14)
        ],
        "logic": [{"task_number": n, "skill_id": "logic.operations"} for n in (2, 9, 15)],
        "programming": [{"task_number": 27, "skill_id": "programming.geometry_clusters"}],
        "multiple_prerequisites": [
            {"task_number": 5, "skill_id": "algorithms.tracing"},
            {"task_number": 8, "skill_id": "number_systems.base_conversion"},
        ],
    }
    courses = {name: build_course(plan) for name, plan in personas.items()}
    assert courses["strong"] == []
    assert len(courses["number_systems"]) == 1  # five wrong contexts, one global node
    assert len(courses["logic"]) == 1
    assert courses["programming"][0].skill_id == "algorithms.tracing"
    assert courses["programming"][-1].skill_id == "programming.geometry_clusters"
    assert courses["programming"][-1].status == "PENDING"
    assert [item.skill_id for item in courses["multiple_prerequisites"]] == [
        "algorithms.tracing", "number_systems.base_conversion"
    ]


def test_mastery_rejects_hinted_transfer_and_cross_skill_evidence():
    path = build_learning_path(16, skill_id="algorithms.recursion")
    for step in MODULE_STEPS[path.skill_id]:
        if step["difficulty"] == "transfer":
            submit_answer(path, "wrong")
        submit_answer(path, step["answers"][0])
    with pytest.raises(ValueError, match="independent"):
        confirm_global_skill_mastery(create_default_learning_dna(2), path.skill_id, path.to_dict())

    clean = build_learning_path(16, skill_id="algorithms.recursion")
    for step in MODULE_STEPS[clean.skill_id]:
        submit_answer(clean, step["answers"][0])
    clean.history[0]["skill_id"] = "logic.operations"
    with pytest.raises(ValueError, match="another global skill"):
        confirm_global_skill_mastery(create_default_learning_dna(3), clean.skill_id, clean.to_dict())

@pytest.mark.parametrize("persona,plan,first", [
    ("recursion", [{"task_number": 16, "skill_id": "algorithms.recursion"}], "algorithms.tracing"),
    ("games", [{"task_number": n, "skill_id": "algorithms.game_strategy"} for n in (19, 20, 21)], "logic.operations"),
    ("strings", [{"task_number": 24, "skill_id": "programming.strings"}], "algorithms.tracing"),
    ("sequences", [{"task_number": 26, "skill_id": "programming.sequences"}, {"task_number": 26, "skill_id": "programming.grouping"}], "algorithms.tracing"),
    ("spreadsheet_dp", [{"task_number": 18, "skill_id": "data.spreadsheets"}, {"task_number": 18, "skill_id": "algorithms.dynamic_programming"}], "logic.operations"),
])
def test_e2e_gap_personas_get_prerequisites_and_distinct_first_module(persona, plan, first):
    course = build_course(plan)
    assert course[0].skill_id == first
    assert len({item.skill_id for item in course}) == len(course)


def test_tasks_19_20_21_share_exactly_one_game_module():
    course = build_course([
        {"task_number": number, "skill_id": "algorithms.game_strategy"}
        for number in (19, 20, 21)
    ])
    game = [item for item in course if item.skill_id == "algorithms.game_strategy"]
    assert len(game) == 1
    assert game[0].related_exam_tasks == (19, 20, 21)
    assert len(course) < 3 + 2  # shared node plus only its two prerequisite branches


def test_course_inserts_prerequisite_with_graph_exam_context_and_unlocks_dependent():
    plan = [{"task_number": 16, "skill_id": "algorithms.recursion"}]
    course = build_course(plan)
    assert [item.skill_id for item in course] == ["algorithms.tracing", "algorithms.recursion"]
    assert course[0].related_exam_tasks == (5, 6, 12)
    assert course[0].status == "READY"
    assert course[1].status == "PENDING"

    rebuilt = build_course(plan, {"algorithms.tracing": {"mastered": True}})
    assert [item.skill_id for item in rebuilt] == ["algorithms.recursion"]
    assert rebuilt[0].status == "READY"


def test_dashboard_renders_inserted_prerequisite_without_duplicating_plan():
    dna = create_default_learning_dna(1)
    dna["trajectory"]["individual_plan"] = [
        {"task_number": 16, "skill_id": "algorithms.recursion", "skill_name": "Рекурсия"}
    ]
    view = build_student_dashboard(dna)
    rendered = __import__(
        "src.services.student_dashboard_service", fromlist=["render_student_dashboard"]
    ).render_student_dashboard(view)
    assert len(view["individual_plan"]) == 1
    assert "Сначала освоить «Трассировка алгоритмов»" in rendered
