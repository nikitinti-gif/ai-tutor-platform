"""Progressive learning paths from prerequisite skills to exam-level EGE tasks.

The first vertical slice covers reasoning task 14. Python owns task structure,
canonical answers and mastery transitions. An LLM may explain a step, but cannot
decide correctness or mastery.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import time

from src.ai_engine.ege_open_variant_2026 import get_open_variant_task
from src.skills.skill_graph import get_task_solution_mode
from src.services.learning_course import MAX_RETRIES, MODULE_STEPS

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

# A fresh exam-level transfer that is not the published open-variant task.
# This prevents a memorised official answer from being counted as mastery.
_EXAM_TRANSFER_VALUE = (
    4 * (1296**2019)
    - 3 * (216**2020)
    + 2 * (36**2021)
    - 6**2022
    - 2027
)


TASK14_LEVELS: tuple[dict, ...] = (
    {
        "id": "digit_value",
        "title": "Значение буквенной цифры",
        "skill_id": "number_systems.digit_property_from_value",
        "support": "В системах счисления после 9 используются буквенные цифры: A=10, B=11, ..., Z=35.",
        "worked_example": "В 16-ричной системе A=10, B=11, C=12, D=13, поэтому следующая цифра E имеет значение 14.",
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
        "worked_example": "В записи 4BD₁₆ значения цифр равны 4, 11 и 13. Чётное среди них только 4, значит ответ для этого примера — 1.",
        "prompt": "В записи 2AE₁₆ сколько цифр имеют чётное числовое значение?",
        "answers": ("3",),
        "difficulty": "basic",
    },
    {
        "id": "place_value",
        "title": "Разрядная структура основания 36",
        "skill_id": "number_systems.large_number_digits",
        "support": "36^k в 36-ричной системе — это 1 и ровно k нулей после неё.",
        "worked_example": "36² в системе с основанием 36 записывается как 100₃₆: после единицы стоят два нуля.",
        "prompt": "Сколько нулей стоит после единицы в 36-ричной записи числа 36^3?",
        "answers": ("3",),
        "difficulty": "basic",
    },
    {
        "id": "constructed_number",
        "title": "Собираем число по степеням основания",
        "skill_id": "number_systems.large_number_digits",
        "support": "Коэффициенты при 36^3, 36^2, 36 и 1 становятся последовательными цифрами записи, если каждый коэффициент от 0 до 35.",
        "worked_example": "Например, 3·36² + 5·36 + 7 имеет запись 357₃₆: коэффициенты становятся цифрами соответствующих разрядов.",
        "prompt": "Число равно 2·36^3 + 3·36^2 + 4·36 + 5. Сколько цифр с чётным значением в его 36-ричной записи?",
        "answers": ("2",),
        "difficulty": "intermediate",
    },
    {
        "id": "exam_analogue",
        "title": "Упрощённый аналог №14",
        "skill_id": "number_systems.large_number_digits",
        "support": "Теперь структура похожа на экзаменационную: найди значение выражения, рассмотри его 36-ричную запись и считай цифры по числовому значению.",
        "prompt": "Найдите количество цифр с чётным значением в 36-ричной записи числа 5·1296^2 − 4·216^2 + 3·36^3 − 2·6^4 − 9.",
        "answers": (str(_even_digit_count_base36(_ANALOGUE_VALUE)),),
        "difficulty": "transfer",
    },
    {
        "id": "exam_task",
        "title": "Открытый вариант КЕГЭ №14",
        "skill_id": "number_systems.large_number_digits",
        "support": "Подсказок больше нет. Это формулировка открытого варианта КЕГЭ-2026.",
        "prompt": get_open_variant_task(14).statement,
        "answers": tuple(item for row in get_open_variant_task(14).answer_rows for item in row),
        "difficulty": "exam",
    },
    {
        "id": "exam_transfer",
        "title": "Независимый экзаменационный перенос",
        "skill_id": "number_systems.large_number_digits",
        "support": "Последняя проверка без подсказок: новая задача того же экзаменационного семейства, которой не было в открытом варианте.",
        "prompt": "Найдите количество цифр с чётным значением в 36-ричной записи числа 4·1296^2019 − 3·216^2020 + 2·36^2021 − 6^2022 − 2027.",
        "answers": (str(_even_digit_count_base36(_EXAM_TRANSFER_VALUE)),),
        "difficulty": "exam_transfer",
    },
)


@dataclass(slots=True)
class LearningPath:
    task_number: int
    solution_mode: str
    skill_id: str = "number_systems.large_number_digits"
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
            skill_id=str(data.get("skill_id", "number_systems.large_number_digits")),
            source=str(data.get("source", "diagnostic_exam")),
            current_index=int(data.get("current_index", 0)),
            status=str(data.get("status", "learning")),
            attempts_on_step=int(data.get("attempts_on_step", 0)),
            history=list(data.get("history", [])),
        )


def build_learning_path(
    task_number: int, *, source: str = "diagnostic_exam", skill_id: str | None = None
) -> LearningPath:
    """Build an executable path for a global skill in an exam context."""
    skill_id = skill_id or ("number_systems.large_number_digits" if task_number == 14 else "")
    if skill_id not in MODULE_STEPS and skill_id != "number_systems.large_number_digits":
        raise ValueError(
            f"Progressive Learning Path was previously only for task 14; "
            f"no production module exists for global skill {skill_id!r}."
        )
    mode = get_task_solution_mode(task_number)
    return LearningPath(task_number=task_number, solution_mode=mode, skill_id=skill_id, source=source)


def _levels(path: LearningPath) -> tuple[dict, ...]:
    if path.skill_id == "number_systems.large_number_digits":
        return TASK14_LEVELS
    return MODULE_STEPS[path.skill_id]


def current_step(path: LearningPath) -> dict | None:
    levels = _levels(path)
    if path.status == "mastered" or path.current_index >= len(levels):
        return None
    step = dict(levels[path.current_index])
    step.setdefault("skill_id", path.skill_id)
    return step


def render_current_step(path: LearningPath) -> str:
    step = current_step(path)
    if step is None:
        return "🏆 Ветка №14 завершена: экзаменационный уровень подтверждён."
    number = path.current_index + 1
    total = len(_levels(path))
    if path.attempts_on_step == 0:
        support = f"\n\n💡 Перед задачей:\n{step['support']}"
    elif path.attempts_on_step >= 2 and step.get("worked_example"):
        support = (
            f"\n\n🧑‍🏫 Разберём похожий пример:\n{step['worked_example']}"
            f"\n\n💡 Теперь вернись к своей задаче:\n{step['support']}"
        )
    else:
        support = f"\n\n💡 Подсказка:\n{step['support']}"
    heading = "ПУТЬ К №14" if path.skill_id == "number_systems.large_number_digits" else f"НАВЫК {path.skill_id} · КОНТЕКСТ №{path.task_number}"
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🪜 {heading} · ШАГ {number}/{total}\n"
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
        if path.current_index >= len(_levels(path)):
            path.status = "mastered"
        return {
            "is_correct": True,
            "status": path.status,
            "completed_step": completed_step,
            "next_step": current_step(path),
        }

    retry_limit_reached = path.attempts_on_step >= MAX_RETRIES
    if retry_limit_reached:
        # Never loop forever on one item. Return to a simpler prerequisite
        # checkpoint and preserve the failed item in history as evidence.
        path.current_index = max(0, path.current_index - 1)
        path.attempts_on_step = 0
    return {
        "is_correct": False,
        "status": path.status,
        "attempts_on_step": path.attempts_on_step,
        "step": step,
        "needs_teaching": path.attempts_on_step >= 2,
        "retry_limit_reached": retry_limit_reached,
    }
