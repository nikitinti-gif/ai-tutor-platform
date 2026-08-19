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
        path = build_learning_path(8 if skill_id == "number_systems.base_conversion" else {
            "logic.operations": 2, "algorithms.tracing": 6,
            "information.units_conversion": 7,
        }[skill_id], skill_id=skill_id)
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
    assert courses["programming"][0].status == "PENDING"
    assert [item.skill_id for item in courses["multiple_prerequisites"]] == [
        "algorithms.tracing", "number_systems.base_conversion"
    ]
