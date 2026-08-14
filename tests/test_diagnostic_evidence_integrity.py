import pytest

from src.ai_engine.diagnostic_evidence_gate import answer_bound_control_probe
from src.ai_engine.diagnostics import (
    apply_live_probe,
    next_control_probe,
    open_diagnostic_case,
)
from src.skills.skill_graph import load_skill_map


def _case(task_number=14):
    return open_diagnostic_case(
        task_number,
        "wrong",
        "expected",
        load_skill_map(),
    )


def test_answer_without_displayed_pending_probe_cannot_create_evidence():
    """STATE_ERROR guard: an unseen question must never become evidence."""
    case = _case(14)
    probe = next_control_probe(case)

    with pytest.raises(ValueError, match="показан|pending|актив"):
        answer_bound_control_probe(case, probe["probe_id"], "2")

    assert len(case["evidence"]) == 1


def test_answer_for_different_probe_id_cannot_be_attached_to_pending_question():
    """A student answer is valid only for the exact probe that was displayed."""
    case = _case(14)
    probe = next_control_probe(case)
    pending = {
        **probe,
        "source": "ai_wording_parameters_python_solver",
        "expected_answers": ("2",),
    }
    case = apply_live_probe(case, pending)

    with pytest.raises(ValueError, match="проб"):
        answer_bound_control_probe(case, "some-other-probe", "2")

    assert len(case["evidence"]) == 1


def test_valid_evidence_contains_complete_question_answer_verdict_chain():
    """Evidence used by Learning DNA must be auditable end to end."""
    case = _case(14)
    probe = next_control_probe(case)
    pending = {
        **probe,
        "source": "ai_wording_parameters_python_solver",
        "expected_answers": ("2",),
    }
    case = apply_live_probe(case, pending)
    updated = answer_bound_control_probe(case, probe["probe_id"], "6")
    evidence = updated["evidence"][-1]

    assert evidence["probe_id"] == probe["probe_id"]
    assert evidence["question"] == probe["prompt"]
    assert evidence["display_prompt"] == probe["prompt"]
    assert evidence["canonical_answer"] == "2"
    assert evidence["student_answer"] == "6"
    assert evidence["validator_result"] is False
    assert evidence["evidence_valid"] is True
