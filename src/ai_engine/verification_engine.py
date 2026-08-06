"""Local answer verifier for the 27-task KЕГЭ exam flow."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .ege_open_variant_2026 import EgeTask, get_open_variant_task


@dataclass(frozen=True, slots=True)
class VerificationResult:
    task_number: int
    is_correct: bool
    normalized_answer: tuple[tuple[str, ...], ...]
    expected_answer: tuple[tuple[str, ...], ...]
    message: str
    api_used: bool = False


_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё]+|[-+]?\d+")


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def normalize_answer(text: str, task: EgeTask) -> tuple[tuple[str, ...], ...]:
    """Normalize Telegram input while preserving the official answer row shape.

    Accepted separators: whitespace, comma, semicolon and line breaks. For tasks
    with several output rows, a single flat sequence is regrouped according to
    the expected row widths, so mobile input remains convenient.
    """
    values = _tokens(text.strip())
    expected_widths = [len(row) for row in task.answer_rows]
    expected_count = sum(expected_widths)
    if len(values) != expected_count:
        return (tuple(values),) if values else tuple()

    rows: list[tuple[str, ...]] = []
    offset = 0
    for width in expected_widths:
        rows.append(tuple(values[offset : offset + width]))
        offset += width
    return tuple(rows)


def verify_answer(task_number: int, student_answer: str) -> VerificationResult:
    task = get_open_variant_task(task_number)
    normalized = normalize_answer(student_answer, task)
    expected = tuple(tuple(value.lower() for value in row) for row in task.answer_rows)
    is_correct = normalized == expected
    if is_correct:
        message = "✅ Верно. Ответ принят."
    elif not normalized:
        message = "⚠️ Ответ пустой. Введите итоговый ответ и отправьте ещё раз."
    else:
        message = "❌ Ответ пока неверный. Попробуйте ещё раз или запросите подсказку."
    return VerificationResult(
        task_number=task_number,
        is_correct=is_correct,
        normalized_answer=normalized,
        expected_answer=expected,
        message=message,
        api_used=False,
    )
