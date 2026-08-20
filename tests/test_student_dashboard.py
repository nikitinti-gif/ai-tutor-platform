import copy

from src.learning_dna.profile import create_default_learning_dna
from src.services.student_dashboard_service import (
    build_student_dashboard,
    render_student_dashboard,
)
from src.services.learning_course import MODULE_STEPS, build_course
from src.skills.skill_graph import load_skill_map


def _node(view, skill_id):
    return next(node for node in view["nodes"] if node["skill_id"] == skill_id)


def test_dashboard_reflects_global_learning_dna_and_exam_score():
    dna = create_default_learning_dna(42)
    dna["skills"] = {
        "number_systems.calculate_remainder": {"status": "confirmed_weak"},
        "logic.operations": {"mastered": True, "mastery_level": 100},
        "programming.sequences": {"status": "suspected"},
    }
    dna["trajectory"]["individual_plan"] = [{
        "skill_id": "number_systems.calculate_remainder",
        "skill_name": "Вычисление остатка",
        "evidence_status": "confirmed",
        "action": "Повторить правило",
    }]
    view = build_student_dashboard(dna, {"attempt": {"results": {"1": True, "2": False}}})

    assert view["exam_score"] == 1
    assert _node(view, "number_systems.calculate_remainder")["status"] == "confirmed_weak"
    assert _node(view, "programming.sequences")["status"] == "suspected"
    assert _node(view, "logic.operations")["status"] == "mastered"
    assert view["individual_plan"] == dna["trajectory"]["individual_plan"]
    assert "🔴" in render_student_dashboard(view)


def test_dashboard_has_prerequisite_edges_and_one_node_for_many_tasks():
    view = build_student_dashboard(create_default_learning_dna(1))
    skill_map = load_skill_map()
    shared = next(skill for skill in skill_map["skills"] if len(skill["exam_tasks"]) > 1)
    nodes = [node for node in view["nodes"] if node["skill_id"] == shared["id"]]
    assert len(nodes) == 1
    assert nodes[0]["exam_tasks"] == shared["exam_tasks"]
    for prerequisite in nodes[0]["prerequisites"]:
        assert {"from": prerequisite, "to": shared["id"]} in view["edges"]


def test_dashboard_updates_same_node_after_mastery():
    dna = create_default_learning_dna(1)
    skill_id = "number_systems.calculate_remainder"
    dna["skills"][skill_id] = {"status": "confirmed_weak"}
    before = build_student_dashboard(dna)
    mastered = copy.deepcopy(dna)
    mastered["skills"][skill_id] = {"mastered": True, "mastery_level": 100}
    after = build_student_dashboard(mastered)
    assert _node(before, skill_id)["status"] == "confirmed_weak"
    assert _node(after, skill_id)["status"] == "mastered"
    assert len([n for n in after["nodes"] if n["skill_id"] == skill_id]) == 1


def _recursion_plan():
    return [{"task_number": 16, "skill_id": "algorithms.recursion"}]


def _dna_with_recursion_plan():
    dna = create_default_learning_dna(1)
    dna["trajectory"]["individual_plan"] = _recursion_plan()
    return dna


def test_dashboard_separates_module_support_from_prerequisite_availability(monkeypatch):
    monkeypatch.setitem(MODULE_STEPS, "algorithms.recursion", MODULE_STEPS["algorithms.tracing"])
    view = build_student_dashboard(_dna_with_recursion_plan())

    tracing = _node(view, "algorithms.tracing")
    recursion = _node(view, "algorithms.recursion")
    assert tracing["course_status"] == "READY"
    assert recursion["module_support"] == "READY_MODULE"
    assert recursion["course_status"] == "BLOCKED_BY_PREREQUISITE"
    assert "Трассировка алгоритмов" in recursion["next_step"]
    assert "Начать learning module" not in render_student_dashboard(view)


def test_dashboard_unlocks_dependent_module_after_prerequisite_mastery(monkeypatch):
    monkeypatch.setitem(MODULE_STEPS, "algorithms.recursion", MODULE_STEPS["algorithms.tracing"])
    dna = _dna_with_recursion_plan()
    dna["skills"]["algorithms.tracing"] = {"mastered": True, "mastery_level": 100}
    view = build_student_dashboard(dna)

    assert _node(view, "algorithms.tracing")["course_status"] == "MASTERED"
    assert _node(view, "algorithms.recursion")["course_status"] == "READY"


def test_dashboard_reports_missing_module_before_prerequisite_block():
    dna = create_default_learning_dna(1)
    dna["trajectory"]["individual_plan"] = [
        {"task_number": 17, "skill_id": "programming.sequences"}
    ]
    node = _node(build_student_dashboard(dna), "programming.sequences")
    assert node["module_support"] == "PENDING_MODULE"
    assert node["course_status"] == "PENDING_MODULE"


def test_dashboard_mastery_wins_regardless_of_module_support():
    dna = create_default_learning_dna(1)
    dna["skills"]["programming.sequences"] = {"mastered": True}
    node = _node(build_student_dashboard(dna), "programming.sequences")
    assert node["module_support"] == "PENDING_MODULE"
    assert node["course_status"] == "MASTERED"


def test_dashboard_course_order_is_course_engine_order(monkeypatch):
    monkeypatch.setitem(MODULE_STEPS, "algorithms.recursion", MODULE_STEPS["algorithms.tracing"])
    dna = _dna_with_recursion_plan()
    expected = build_course(_recursion_plan(), dna["skills"])
    view = build_student_dashboard(dna)
    assert [item["skill_id"] for item in view["course"]] == [item.skill_id for item in expected]
