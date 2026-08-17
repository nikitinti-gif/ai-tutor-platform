"""Progressive learning paths from prerequisite skills to exam-level EGE tasks.

The first vertical slice covers reasoning task 14.  The service is deliberately
provider-independent: Python owns task structure, canonical answers and state
transitions.  An LLM may later explain a step, but cannot decide mastery.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import time

from src.ai_engine.ege_open_variant_2026 import get_open_variant_task
from src.skills.skill_graph import get_task_solution_mode

_DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _to_base36(value: int) -> str:
    if value < 0:
        raise ValueError("Learning-path examples must be non-negative.")
    if value == 0:
        return "0"
    result = ""
    while value:
        value, remainder = divmod(value, 36)
        result = _DIGITS[remainder] + result
    return result


def _even_digit_count_base36(value: int) -> int:
    return sum(_DIGITS.index(symbol) % 2 == 0 for symbol in _to_base36(value))


_ANALOGUE_VALUE = (
    5 * (1296**2)
    - 4 * (216**2)
    + 3 * (36**3)
    - 2 * (6**4)
    - 9
)


TASK14_LEVELS: tuple[dict, ...] = (
    {
        "id": "digit_value",
        "title": "Значение буквенной цифры",
        "skill_id": "number_systems.digit_property_from_value",
        "support": "В системах счисления после 9 используются буквенные цифры: A=10, B=11, ..., Z=35.",
        "prompt": "В 16-ричной системе цифра E имеет какое десятичное значение?",
        "answers": ("14",),
        "difficulty": "foundation",
    },
    {
        "id": "small_conversion",
        "title": "Небольшой перевод в другую систему",
        "skill_id": "number_systems.base_conversion",
        "support": "При переводе дели число на основание и читай остатки снизу вверх.",
        "worked_example": "Похожий пример: 45 = 2·16 + 13. Остаток 13 — это D, поэтому 45₁₀ = 2D₁₆. Теперь тем же способом разложи 47.",
        "prompt": "Переведи 47 из десятичной системы в 16-ричную. Запиши только результат.",
        "answers": ("2F", "2f"),
        "difficulty": "foundation",
    },
    {
        "id": "digit_property",
        "title": "Свойство цифр записи",
        "skill_id": "number_systems.digit_property_from_value",
        "support": "Чётность буквенной цифры проверяется по её числовому значению: A=10, E=14 и т.д.",
        "prompt": "В записи 2AE₁₆ сколько цифр имеют чётное числовое значение?",
        "answers": ("3",),
        "difficulty": "basic",
    },
    {
        "id": "place_value",
        "title": "Разрядная структура основания 36",
        "skill_id": "number_systems.large_number_digits",
        "support": "36^k в 36-ричной системе — это 1 и ровно k нулей после неё.",
        "prompt": "Сколько нулей стоит после единицы в 36-ричной записи числа 36^3?",
        "answers": ("3",),
        "difficulty": "basic",
    },
    {
        "id": "constructed_number",
        "title": "Собираем число по степеням основания",
        "skill_id": "number_systems.large_number_digits",
        "support": "Коэффициенты при 36^3, 36^2, 36 и 1 становятся последовательными цифрами записи, если каждый коэффициент от 0 до 35.",
        "prompt": "Число равно 2·36^3 + 3·36^2 + 4·36 + 5. Сколько цифр с чётным значением в его 36-ричной записи?",
        "answers": ("2",),
        "difficulty": "intermediate",
    },
    {
        "id": "exam_analogue",
        "title": "Упрощённый аналог №14",
        "skill_id": "number_systems.large_number_digits",
        "support": "Теперь структура похожа на экзаменационную: сначала найди значение выражения, затем рассматривай его 36-ричную запись и считай цифры по числовому значению.",
        "prompt": "Найдите количество цифр с чётным значением в 36-ричной записи числа 5·1296^2 − 4·216^2 + 3·36^3 − 2·6^4 − 9.",
        "answers": (str(_even_digit_count_base36(_ANALOGUE_VALUE)),),
        "difficulty": "transfer",
    },
    {
        "id": "exam_task",
        "title": "Экзаменационный уровень №14",
        "skill_id": "number_systems.large_number_digits",
        "support": "Подсказок больше нет. Это формулировка открытого варианта КЕГЭ-2026.",
        "prompt": get_open_variant_task(14).statement,
        "answers": tuple(item for row in get_open_variant_task(14).answer_rows for item in row),
        "difficulty": "exam",
    },
)


@dataclass(slots=True)
class LearningPath:
    task_number: int
    solution_mode: str
    source: str = "diagnostic_exam"
    current_index: int = 0
    status: str = "learning"
    attempts_on_step: int = 0
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "LearningPath":
        return cls(
            task_number=int(data["task_number"]),
            solution_mode=str(data["solution_mode"]),
            source=str(data.get("source", "diagnostic_exam")),
            current_index=int(data.get("current_index", 0)),
            status=str(data.get("status", "learning")),
            attempts_on_step=int(data.get("attempts_on_step", 0)),
            history=list(data.get("history", [])),
        )


def build_learning_path(task_number: int, *, source: str = "diagnostic_exam") -> LearningPath:
    """Build the first production learning-path slice.

    Only task 14 is enabled until this vertical slice passes Telegram E2E.
    Programming tasks intentionally use a different future engine.
    """
    if task_number != 14:
        raise ValueError("Progressive Learning Path is currently enabled only for task 14.")
    mode = get_task_solution_mode(task_number)
    if mode != "reasoning":
        raise ValueError("This learning path is only for reasoning tasks.")
    return LearningPath(task_number=task_number, solution_mode=mode, source=source)


def current_step(path: LearningPath) -> dict | None:
    if path.status == "mastered" or path.current_index >= len(TASK14_LEVELS):
        return None
    return TASK14_LEVELS[path.current_index]


def render_current_step(path: LearningPath) -> str:
    step = current_step(path)
    if step is None:
        return "🏆 Ветка №14 завершена: экзаменационный уровень подтверждён."
    number = path.current_index + 1
    total = len(TASK14_LEVELS)
    support = ""
    if path.attempts_on_step == 0:
        support = f"\n\n💡 Перед задачей:\n{step['support']}"
    elif path.attempts_on_step >= 2 and step.get("worked_example"):
        support = (
            f"\n\n🧑‍🏫 Разберём похожий пример:\n{step['worked_example']}"
            f"\n\n💡 Теперь вернись к своей задаче:\n{step['support']}"
        )
    else:
        support = f"\n\n💡 Подсказка:\n{step['support']}"
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🪜 ПУТЬ К №14 · ШАГ {number}/{total}\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"{step['title']} · уровень: {step['difficulty']}"
        f"{support}\n\n"
        f"✍️ {step['prompt']}\n\n"
        "Отправь только ответ."
    )


def submit_answer(path: LearningPath, answer: str) -> dict:
    step = current_step(path)
    if step is None:
        raise ValueError("Learning Path already completed.")
    normalized = answer.strip().upper().replace("Ё", "Е")
    expected = {str(item).strip().upper().replace("Ё", "Е") for item in step["answers"]}
    is_correct = normalized in expected
    path.attempts_on_step += 1
    path.history.append(
        {
            "step_id": step["id"],
            "skill_id": step["skill_id"],
            "difficulty": step["difficulty"],
            "student_answer": answer,
            "canonical_answer": str(step["answers"][0]),
            "validator_result": is_correct,
            "timestamp": time.time(),
        }
    )

    if is_correct:
        completed_step = step["id"]
        path.current_index += 1
        path.attempts_on_step = 0
        if path.current_index >= len(TASK14_LEVELS):
            path.status = "mastered"
        return {
            "is_correct": True,
            "status": path.status,
            "completed_step": completed_step,
            "next_step": current_step(path),
        }

    # Wrong answers do not create a weakness by themselves.  Stay on the same
    # level and make the support explicit.  A later Tutor policy may insert an
    # explanation or worked example after repeated failures.
    return {
        "is_correct": False,
        "status": path.status,
        "attempts_on_step": path.attempts_on_step,
        "step": step,
        "needs_teaching": path.attempts_on_step >= 2,
    }
