"""Strict evidence gate for diagnostic mini-probes.

A student's answer may become diagnostic evidence only when it is bound to the
exact probe that was shown. This module keeps the integrity contract explicit
while the diagnostic engine is migrated to fail-closed evidence handling.
"""
from __future__ import annotations

from copy import deepcopy

from src.ai_engine.diagnostics import (
    CONTROL_PROBES,
    _gap_for_operation,
    _normalize_probe_answer,
    record_control_probe,
)


def answer_bound_control_probe(case: dict, probe_id: str, answer: str) -> dict:
    """Validate an answer only against the exact currently displayed probe."""
    pending = case.get("pending_probe") or {}
    pending_probe_id = str(pending.get("probe_id", "")).strip()
    if not pending_probe_id:
        raise ValueError("Нет активной показанной диагностической пробы.")
    if pending_probe_id != probe_id:
        raise ValueError("Ответ не соответствует активной диагностической пробе.")

    base_probe_id = str(
        pending.get("base_probe_id") or probe_id.split(":retry", 1)[0]
    )
    probes = CONTROL_PROBES.get(int(case.get("task_number", 0)), ())
    probe = next((item for item in probes if item["id"] == base_probe_id), None)
    if probe is None:
        raise ValueError("Контрольная проба не найдена для этого задания.")
    if any(
        item.get("kind") == "control_probe" and item.get("probe_id") == probe_id
        for item in case.get("evidence", [])
    ):
        raise ValueError("Эта контрольная проба уже пройдена.")

    operations = case.get("operations", [])
    operation_index = probe["operation_index"]
    if not 0 <= operation_index < len(operations):
        raise ValueError("Диагностическая проба ссылается на неизвестный шаг.")
    tested_step = operations[operation_index]

    expected_answers = tuple(
        pending.get("expected_answers") or probe["expected_answers"]
    )
    if not expected_answers:
        raise ValueError("У диагностической пробы отсутствует эталонный ответ.")
    normalized_answer = _normalize_probe_answer(answer)
    is_correct = normalized_answer in {
        _normalize_probe_answer(value) for value in expected_answers
    }

    updated = record_control_probe(
        case,
        probe_id=probe_id,
        tested_step=tested_step,
        is_correct=is_correct,
        observed_answer=answer,
        gap=_gap_for_operation(int(case.get("task_number", 0)), operation_index),
        probe_role=pending.get("probe_role", "discrimination"),
    )
    updated.pop("pending_probe", None)

    evidence = updated["evidence"][-1]
    evidence.update(
        {
            "base_probe_id": base_probe_id,
            "question": pending.get("prompt") or probe["prompt"],
            "canonical_question": pending.get("canonical_prompt") or probe["prompt"],
            "canonical_answer": str(expected_answers[0]),
            "accepted_answers": [str(value) for value in expected_answers],
            "student_answer": answer,
            "validator_result": is_correct,
            "evidence_valid": True,
            "probe_source": pending.get("source", "local_fallback"),
        }
    )
    evidence["display_prompt"] = evidence["question"]
    return updated


def valid_diagnostic_evidence(case: dict) -> list[dict]:
    """Return only complete, auditable evidence allowed to affect Learning DNA."""
    required = (
        "probe_id",
        "question",
        "canonical_answer",
        "student_answer",
        "validator_result",
    )
    return [
        deepcopy(item)
        for item in case.get("evidence", [])
        if item.get("kind") == "control_probe"
        and item.get("evidence_valid") is True
        and all(item.get(field) is not None for field in required)
    ]
