"""Session helpers for the 27-task KЕГЭ open variant flow."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from src.ai_engine.ege_open_variant_2026 import OPEN_VARIANT_2026, EgeTask
from src.ai_engine.verification_engine import VerificationResult, verify_answer


@dataclass(slots=True)
class ExamAttempt:
    current_task: int = 1
    answers: dict[int, str] = field(default_factory=dict)
    results: dict[int, bool] = field(default_factory=dict)

    @property
    def finished(self) -> bool:
        return self.current_task > 27

    @property
    def correct_count(self) -> int:
        return sum(self.results.values())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "ExamAttempt":
        data = data or {}
        return cls(
            current_task=int(data.get("current_task", 1)),
            answers={int(k): str(v) for k, v in data.get("answers", {}).items()},
            results={int(k): bool(v) for k, v in data.get("results", {}).items()},
        )


def get_task(number: int) -> EgeTask:
    return OPEN_VARIANT_2026[number]


def render_task(number: int) -> str:
    task = get_task(number)
    attachment = (
        "\n📎 Для решения используется файл-приложение варианта."
        if task.attachment_required
        else ""
    )
    return (
        f"📝 КЕГЭ 2026 · задание {number}/27\n"
        f"Тема: {task.title}{attachment}\n\n"
        f"{task.prompt}\n\n"
        "Отправьте только итоговый ответ. Для выхода: /cancel_ege"
    )


def submit_answer(attempt: ExamAttempt, answer: str) -> VerificationResult:
    if attempt.finished:
        raise ValueError("Экзамен уже завершён.")
    number = attempt.current_task
    result = verify_answer(number, answer)
    attempt.answers[number] = answer
    attempt.results[number] = result.is_correct
    attempt.current_task += 1
    return result


def render_summary(attempt: ExamAttempt) -> str:
    correct = attempt.correct_count
    wrong = [str(n) for n in range(1, 28) if not attempt.results.get(n, False)]
    wrong_text = ", ".join(wrong) if wrong else "нет"
    return (
        "🏁 Вариант завершён\n\n"
        f"Верных заданий: {correct} из 27\n"
        f"Неверные задания: {wrong_text}\n\n"
        "Это первичный результат по кратким ответам. AI и Vision не использовались."
    )
