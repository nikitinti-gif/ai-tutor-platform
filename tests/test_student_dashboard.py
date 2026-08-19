import copy

from src.learning_dna.profile import create_default_learning_dna
from src.services.student_dashboard_service import (
    build_student_dashboard,
    render_student_dashboard,
)
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
