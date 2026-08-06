"""Session helpers for the 27-task KЕГЭ open variant flow."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace

from src.ai_engine.ege_open_variant_2026 import (
    EgeTask,
    OFFICIAL_FILES_URL,
    OPEN_VARIANT_2026,
)
from src.ai_engine.verification_engine import VerificationResult, verify_answer

TOTAL_TASKS = 27
PROGRESS_WIDTH = 12


@dataclass(slots=True)
class ExamAttempt:
    current_task: int = 1
    answers: dict[int, str] = field(default_factory=dict)
    results: dict[int, bool] = field(default_factory=dict)
    skipped: list[int] = field(default_factory=list)

    @property
    def finished(self) -> bool:
        return self.current_task > TOTAL_TASKS

    @property
    def correct_count(self) -> int:
        return sum(self.results.values())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "ExamAttempt":
        data = data or {}
        return cls(
            int(data.get("current_task", 1)),
            {int(k): str(v) for k, v in data.get("answers", {}).items()},
            {int(k): bool(v) for k, v in data.get("results", {}).items()},
            [int(x) for x in data.get("skipped", [])],
        )


def get_task(number: int) -> EgeTask:
    return OPEN_VARIANT_2026[number]


def _progress_bar(completed: int) -> str:
    completed = max(0, min(completed, TOTAL_TASKS))
    filled = round(PROGRESS_WIDTH * completed / TOTAL_TASKS)
    return "█" * filled + "░" * (PROGRESS_WIDTH - filled)


def _progress_text(attempt: ExamAttempt) -> str:
    completed = len(attempt.results)
    wrong_count = completed - attempt.correct_count - len(attempt.skipped)
    return (
        f"{_progress_bar(completed)} {completed}/{TOTAL_TASKS}\n"
        f"✅ {attempt.correct_count}   "
        f"❌ {max(0, wrong_count)}   "
        f"⏭ {len(attempt.skipped)}"
    )


def render_task(number: int) -> str:
    task = get_task(number)
    attachment_note = ""
    if task.attachment_required:
        attachment_note = (
            "\n\n📎 Для выполнения нужен файл варианта:\n"
            f"{OFFICIAL_FILES_URL}"
        )

    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎓 КЕГЭ 2026\n"
        f"Задание {number} из {TOTAL_TASKS}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📚 {task.title}\n\n"
        f"{task.statement}"
        f"{attachment_note}\n\n"
        f"✍️ {task.prompt}\n\n"
        "/skip_ege · /finish_ege · /cancel_ege"
    )


def submit_answer(attempt: ExamAttempt, answer: str) -> VerificationResult:
    if attempt.finished:
        raise ValueError("Экзамен уже завершён.")

    task_number = attempt.current_task
    result = verify_answer(task_number, answer)
    attempt.answers[task_number] = answer
    attempt.results[task_number] = result.is_correct
    attempt.current_task += 1

    status = "✅ Верно!" if result.is_correct else "❌ Ответ неверный."
    feedback = f"{status}\n\n📊 {_progress_text(attempt)}"
    return replace(result, message=feedback)


def skip_task(attempt: ExamAttempt) -> int:
    if attempt.finished:
        raise ValueError("Экзамен уже завершён.")

    task_number = attempt.current_task
    if task_number not in attempt.skipped:
        attempt.skipped.append(task_number)
    attempt.results[task_number] = False
    attempt.current_task += 1
    return task_number


def render_summary(attempt: ExamAttempt) -> str:
    checked = sorted(attempt.results)
    wrong = [
        str(number)
        for number in checked
        if not attempt.results.get(number, False) and number not in attempt.skipped
    ]
    skipped = ", ".join(map(str, attempt.skipped)) if attempt.skipped else "нет"
    accuracy = round(attempt.correct_count * 100 / len(checked)) if checked else 0

    if attempt.correct_count >= 24:
        level = "🏆 Отличный результат"
    elif attempt.correct_count >= 18:
        level = "👍 Хорошая база"
    elif attempt.correct_count >= 10:
        level = "📚 Есть темы для повторения"
    else:
        level = "🧭 Нужен пошаговый план подготовки"

    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🏁 ВАРИАНТ ЗАВЕРШЁН\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{level}\n\n"
        f"✅ Верных: {attempt.correct_count}\n"
        f"📝 Проверено: {len(checked)} из {TOTAL_TASKS}\n"
        f"🎯 Точность: {accuracy}%\n\n"
        f"❌ Неверные: {', '.join(wrong) if wrong else 'нет'}\n"
        f"⏭ Пропущенные: {skipped}\n\n"
        "Проверка выполнена локально — без AI и Vision."
    )
