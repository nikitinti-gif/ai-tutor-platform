"""Evidence-based local diagnostics for completed KЕГЭ attempts.

The module deliberately separates a suspected error from a confirmed one.
An incorrect final answer is enough to open a case, but never enough to claim
that a particular reasoning step failed.
"""

from __future__ import annotations

from copy import deepcopy


DIAGNOSIS_NEEDS_EVIDENCE = "needs_evidence"
DIAGNOSIS_PROBABLE = "probable"
DIAGNOSIS_CONFIRMED = "confirmed"


def _task_definition(task_number: int, skill_map: dict) -> dict:
    task = next(
        (item for item in skill_map.get("tasks", []) if item.get("number") == task_number),
        None,
    )
    if task is None:
        raise ValueError(f"В карте навыков отсутствует задание {task_number}.")
    return task


def open_diagnostic_case(
    task_number: int,
    student_answer: str,
    expected_answer: str,
    skill_map: dict,
) -> dict:
    """Create an unresolved case without inventing a failed step."""
    task = _task_definition(task_number, skill_map)
    return {
        "task_number": task_number,
        "task_title": task.get("title", f"Задание {task_number}"),
        "student_answer": student_answer,
        "expected_answer": expected_answer,
        "skill_ids": list(task.get("skills", [])),
        "operations": list(task.get("operations", [])),
        "candidate_errors": list(task.get("typical_errors", [])),
        "failed_step": None,
        "error_type": None,
        "status": DIAGNOSIS_NEEDS_EVIDENCE,
        "confidence": 0.0,
        "evidence": [
            {
                "kind": "incorrect_final_answer",
                "value": student_answer,
                "proves_failed_step": False,
            }
        ],
        "learning_action": None,
    }


def record_student_step(case: dict, operation_index: int) -> dict:
    """Record self-report as a hypothesis, never as confirmation."""
    updated = deepcopy(case)
    operations = updated.get("operations", [])
    if operation_index < 0 or operation_index >= len(operations):
        raise ValueError("Некорректный номер шага решения.")
    failed_step = operations[operation_index]
    updated["failed_step"] = failed_step
    updated["status"] = DIAGNOSIS_PROBABLE
    updated["confidence"] = 0.45
    updated["evidence"].append(
        {
            "kind": "student_self_report",
            "value": failed_step,
            "proves_failed_step": False,
        }
    )
    return updated


def record_control_probe(
    case: dict,
    *,
    probe_id: str,
    tested_step: str,
    is_correct: bool,
    observed_answer: str,
) -> dict:
    """Apply an independently checked mini-probe to a diagnostic case."""
    if not probe_id.strip() or not tested_step.strip():
        raise ValueError("Контрольная проба должна иметь ID и проверяемый шаг.")
    updated = deepcopy(case)
    updated["evidence"].append(
        {
            "kind": "control_probe",
            "probe_id": probe_id,
            "tested_step": tested_step,
            "is_correct": bool(is_correct),
            "value": observed_answer,
            "proves_failed_step": not is_correct,
        }
    )
    if is_correct:
        updated["status"] = DIAGNOSIS_NEEDS_EVIDENCE
        updated["confidence"] = 0.0
        updated["failed_step"] = None
        updated["error_type"] = None
        updated["learning_action"] = None
    else:
        updated["status"] = DIAGNOSIS_CONFIRMED
        updated["confidence"] = 0.95
        updated["failed_step"] = tested_step
        updated["error_type"] = f"failed_step:{probe_id}"
        updated["learning_action"] = f"Отработать шаг: {tested_step}."
    return updated


def confirmed_cases(cases: list[dict]) -> list[dict]:
    """Return only evidence-backed cases allowed to affect Learning DNA."""
    return [
        deepcopy(case)
        for case in cases
        if case.get("status") == DIAGNOSIS_CONFIRMED
        and any(
            item.get("kind") == "control_probe" and item.get("proves_failed_step")
            for item in case.get("evidence", [])
        )
    ]
