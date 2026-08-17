"""Curated EGE task bank with local Python validation.

External catalogues are used as provenance/catalogue references, not as the
runtime source of truth.  Each task is curated into the repository, tagged by
family and checked by a deterministic Python solver before it can be issued.
"""
from __future__ import annotations

from dataclasses import dataclass

_DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@dataclass(frozen=True, slots=True)
class CuratedEgeTask:
    task_id: str
    task_number: int
    family_id: str
    source_name: str
    source_problem_id: str
    source_url: str
    source_note: str
    prompt: str
    canonical_answer: str
    skill_ids: tuple[str, ...]


def _to_base(value: int, base: int) -> str:
    if value == 0:
        return "0"
    out = ""
    while value:
        value, r = divmod(value, base)
        out = _DIGITS[r] + out
    return out


def _solve_89751() -> str:
    value = 5 * 1296**2021 - 4 * 216**2022 + 3 * 36**2023 - 2 * 6**2024 - 2025
    return str(sum(_DIGITS.index(ch) % 2 == 0 for ch in _to_base(value, 36)))


def _solve_92256() -> str:
    value = 4 * 16**25 + 2 * 8**30 - 64**10
    return str(_to_base(value, 2).count("0"))


def _solve_92258() -> str:
    best_x = None
    best_zeros = -1
    for x in range(1, 2030):
        value = 5**150 + 5**100 - x
        zeros = _to_base(value, 5).count("0")
        if zeros > best_zeros:
            best_zeros = zeros
            best_x = x
    return str(best_x)


TASK14_BANK: tuple[CuratedEgeTask, ...] = (
    CuratedEgeTask(
        task_id="reshuege-89751",
        task_number=14,
        family_id="large_power_digit_property",
        source_name="РЕШУ ЕГЭ / ФИПИ",
        source_problem_id="89751",
        source_url="https://inf-ege.sdamgia.ru/problem?id=89751",
        source_note="ЕГЭ-2026, досрочная волна 07.04.2026, вариант ФИПИ",
        prompt=(
            "Определите количество цифр с чётным числовым значением в 36-ричной записи числа:\n"
            "5·1296^2021 − 4·216^2022 + 3·36^2023 − 2·6^2024 − 2025."
        ),
        canonical_answer=_solve_89751(),
        skill_ids=("number_systems.large_number_digits", "number_systems.digit_property_from_value"),
    ),
    CuratedEgeTask(
        task_id="reshuege-92256",
        task_number=14,
        family_id="large_power_count_digit",
        source_name="РЕШУ ЕГЭ",
        source_problem_id="92256",
        source_url="https://inf-ege.sdamgia.ru/test?id=20691883",
        source_note="ЕГЭ-2026, основная волна 18.06.2026, подборка Школково",
        prompt=(
            "Значение выражения 4·16^25 + 2·8^30 − 64^10 записали в двоичной системе. "
            "Сколько цифр 0 содержит эта запись?"
        ),
        canonical_answer=_solve_92256(),
        skill_ids=("number_systems.large_number_digits",),
    ),
    CuratedEgeTask(
        task_id="reshuege-92258",
        task_number=14,
        family_id="parameter_maximize_digit_count",
        source_name="РЕШУ ЕГЭ",
        source_problem_id="92258",
        source_url="https://inf-ege.sdamgia.ru/problem?id=92258",
        source_note="ЕГЭ-2026, основная волна 18.06.2026, подборка Школково",
        prompt=(
            "Число 5^150 + 5^100 − x, где 0 < x < 2030, записывают в пятеричной системе. "
            "Найдите наименьшее x, при котором количество нулей в записи максимально."
        ),
        canonical_answer=_solve_92258(),
        skill_ids=("number_systems.large_number_digits", "algorithms.parameter_search"),
    ),
)


def task14_bank() -> tuple[CuratedEgeTask, ...]:
    return TASK14_BANK


def get_task(task_id: str) -> CuratedEgeTask:
    for task in TASK14_BANK:
        if task.task_id == task_id:
            return task
    raise KeyError(task_id)


def choose_task14(*, exclude_ids: set[str] | None = None, family_id: str | None = None) -> CuratedEgeTask:
    excluded = exclude_ids or set()
    for task in TASK14_BANK:
        if task.task_id in excluded:
            continue
        if family_id is not None and task.family_id != family_id:
            continue
        return task
    raise LookupError("No unused curated task matches the requested filters.")


def validate_answer(task_id: str, student_answer: str) -> bool:
    task = get_task(task_id)
    return student_answer.strip().upper() == task.canonical_answer.strip().upper()


def render_task(task: CuratedEgeTask) -> str:
    return (
        f"📚 КЕГЭ №{task.task_number} · задача из проверенного банка\n\n"
        f"{task.prompt}\n\n"
        f"Источник: {task.source_name}, №{task.source_problem_id}.\n"
        "Ответ проверяет Python локально; ответ сайта не используется как валидатор.\n\n"
        "Отправь только итоговый ответ."
    )
