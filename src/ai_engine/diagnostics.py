"""Evidence-based local diagnostics for completed KЕГЭ attempts.

The module deliberately separates a suspected error from a confirmed one.
An incorrect final answer is enough to open a case, but never enough to claim
that a particular reasoning step failed.
"""

from __future__ import annotations

from copy import deepcopy
import re


DIAGNOSIS_NEEDS_EVIDENCE = "needs_evidence"
DIAGNOSIS_PROBABLE = "probable"
DIAGNOSIS_CONFIRMED = "confirmed"


# The first production-quality probe set.  Each probe checks exactly one
# operation from the official task map and has a locally verifiable answer.
# Further KЕГЭ tasks must use this same contract; free-form AI judgements are
# deliberately not accepted as diagnostic evidence.
CONTROL_PROBES = {
    14: (
        {
            "id": "task14_remainder_v1",
            "operation_index": 0,
            "prompt": "Какой остаток получится при делении 254 на 36?",
            "expected_answers": ("2",),
        },
        {
            "id": "task14_digit_property_v1",
            "operation_index": 1,
            "prompt": (
                "Сколько цифр с чётным значением среди цифр "
                "A, B, C, D в 36-ричной системе?"
            ),
            "expected_answers": ("2",),
        },
        {
            "id": "task14_count_all_digits_v1",
            "operation_index": 2,
            "prompt": (
                "При разборе числа получены цифры 2, 0, 4, 0, 6. "
                "Сколько среди них цифр с чётным значением?"
            ),
            "expected_answers": ("5",),
        },
    ),
}


def _normalize_probe_answer(value: str) -> str:
    return " ".join(re.findall(r"[a-zа-яё]+|[-+]?\d+", value.lower()))


def validate_control_probes(skill_map: dict) -> None:
    """Reject probes that do not point to a real operation in the skill map."""
    for task_number, probes in CONTROL_PROBES.items():
        task = _task_definition(task_number, skill_map)
        operations = task.get("operations", [])
        seen_ids: set[str] = set()
        for probe in probes:
            probe_id = str(probe.get("id", "")).strip()
            operation_index = probe.get("operation_index")
            expected = probe.get("expected_answers", ())
            if not probe_id or probe_id in seen_ids:
                raise ValueError(f"Некорректный ID пробы задания {task_number}.")
            if not isinstance(operation_index, int) or not 0 <= operation_index < len(operations):
                raise ValueError(f"Проба {probe_id} ссылается на неизвестный шаг.")
            if not probe.get("prompt") or not expected:
                raise ValueError(f"Проба {probe_id} не имеет вопроса или ответа.")
            seen_ids.add(probe_id)


def next_control_probe(case: dict) -> dict | None:
    """Return the next unchecked local probe for a diagnostic case."""
    probes = CONTROL_PROBES.get(int(case.get("task_number", 0)), ())
    completed = {
        item.get("probe_id")
        for item in case.get("evidence", [])
        if item.get("kind") == "control_probe"
    }
    operations = case.get("operations", [])
    for probe in probes:
        if probe["id"] not in completed:
            operation_index = probe["operation_index"]
            return {
                "probe_id": probe["id"],
                "prompt": probe["prompt"],
                "tested_step": operations[operation_index],
            }
    return None


def answer_control_probe(case: dict, probe_id: str, answer: str) -> dict:
    """Verify a mini-probe locally and apply its evidence to the case."""
    probes = CONTROL_PROBES.get(int(case.get("task_number", 0)), ())
    probe = next((item for item in probes if item["id"] == probe_id), None)
    if probe is None:
        raise ValueError("Контрольная проба не найдена для этого задания.")
    if any(
        item.get("kind") == "control_probe" and item.get("probe_id") == probe_id
        for item in case.get("evidence", [])
    ):
        raise ValueError("Эта контрольная проба уже пройдена.")
    operations = case.get("operations", [])
    tested_step = operations[probe["operation_index"]]
    normalized = _normalize_probe_answer(answer)
    is_correct = normalized in {
        _normalize_probe_answer(value) for value in probe["expected_answers"]
    }
    return record_control_probe(
        case,
        probe_id=probe_id,
        tested_step=tested_step,
        is_correct=is_correct,
        observed_answer=answer,
    )


def confirmed_case_to_check_result(case: dict) -> dict:
    """Convert evidence-backed diagnosis to the existing Learning DNA contract."""
    if case not in confirmed_cases([case]):
        raise ValueError("В Learning DNA можно передать только подтверждённую ошибку.")
    skill_ids = case.get("skill_ids", [])
    return {
        "status": "has_error",
        "topic": case.get("task_title", f"Задание {case.get('task_number')}"),
        "skill_id": skill_ids[0] if skill_ids else None,
        "error_type": case.get("error_type"),
        "confidence": case.get("confidence"),
        "feedback": f"Подтверждена ошибка на шаге: {case.get('failed_step')}.",
        "recommendation": case.get("learning_action"),
        "diagnostic_evidence": deepcopy(case.get("evidence", [])),
        "source": "local_control_probe",
    }


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
