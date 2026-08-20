"""Data-driven personal course orchestration over global atomic skills.

The course is deliberately skill-first: exam numbers are evidence contexts, not
mastery identities.  Only modules with deterministic validators and an unseen
transfer are advertised as executable.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.skills.skill_graph import get_skill, load_skill_map, prerequisite_path

LEVELS = ("foundation", "basic", "intermediate", "transfer", "exam", "exam_transfer")
MAX_RETRIES = 4


def _step(step_id: str, difficulty: str, prompt: str, answer: str, instruction: str, example: str) -> dict:
    return {
        "id": step_id, "title": difficulty.replace("_", " ").title(),
        "difficulty": difficulty, "prompt": prompt,
        "answers": (answer,), "support": instruction, "worked_example": example,
        "validator": "normalized_exact", "evidence_type": difficulty,
        "success_transition": "next", "failure_transition": "hint_ladder",
    }


# Small, controlled items are intentionally stored with their answers.  Python,
# rather than an LLM, remains the source of truth.
MODULE_STEPS: dict[str, tuple[dict, ...]] = {
    "number_systems.base_conversion": (
        _step("ns_foundation", "foundation", "Чему равен остаток от деления 29 на 2?", "1", "Остаток всегда меньше основания.", "14 делится на 2 без остатка: остаток 0."),
        _step("ns_basic", "basic", "Переведи 13₁₀ в двоичную систему.", "1101", "Дели на 2 и читай остатки снизу вверх.", "10₁₀ = 1010₂."),
        _step("ns_intermediate", "intermediate", "Переведи 47₁₀ в шестнадцатеричную систему.", "2F", "A=10, ..., F=15.", "45₁₀ = 2D₁₆."),
        _step("ns_transfer", "transfer", "Переведи 101101₂ в десятичную систему.", "45", "Сложи степени двойки в разрядах с единицами.", "1010₂ = 8+2 = 10."),
        _step("ns_exam", "exam", "Число N=37. К его двоичной записи приписали 01. Каково новое число в десятичной системе?", "149", "Приписывание двух битов умножает на 4, затем добавь значение суффикса.", "Для 10 и суффикса 11: 10·4+3=43."),
        _step("ns_exam_transfer", "exam_transfer", "Число N=26. К двоичной записи приписали 11. Каково новое число в десятичной системе?", "107", "Реши независимо, без подсказки по промежуточным действиям.", "Для другого числа проверь результат обратным переводом."),
    ),
    "logic.operations": (
        _step("logic_foundation", "foundation", "Вычисли НЕ 0. Ответ: 0 или 1.", "1", "НЕ меняет 0 на 1 и 1 на 0.", "НЕ 1 = 0."),
        _step("logic_basic", "basic", "Вычисли 1 И 0.", "0", "И равно 1, только когда обе части равны 1.", "1 И 1 = 1."),
        _step("logic_intermediate", "intermediate", "Вычисли (НЕ 0) И (1 ИЛИ 0).", "1", "Сначала скобки и НЕ, затем И.", "(НЕ 1) И 1 = 0."),
        _step("logic_transfer", "transfer", "Вычисли (1 → 0) ИЛИ 0.", "0", "Импликация ложна только для 1→0.", "0→1 равно 1."),
        _step("logic_exam", "exam", "Для x=1,y=0 вычисли: (x И НЕ y) → y.", "0", "Подставь значения и соблюдай приоритет операций.", "При x=0,y=1 левая часть равна 0, поэтому импликация истинна."),
        _step("logic_exam_transfer", "exam_transfer", "Для x=0,y=1 вычисли: НЕ(x ИЛИ y) ↔ x.", "1", "Эквивалентность истинна при равных значениях частей.", "Сначала независимо вычисли обе стороны ↔."),
    ),
    "algorithms.tracing": (
        _step("trace_foundation", "foundation", "x=3; x=x+2. Чему равен x?", "5", "Выполняй команды строго по порядку.", "x=4; x=x+1 даёт 5."),
        _step("trace_basic", "basic", "x=2; повторить 3 раза: x=x+2. Чему равен x?", "8", "Запиши значение после каждой итерации.", "Из 1 после двух прибавлений 3 получим 7."),
        _step("trace_intermediate", "intermediate", "x=5; если x нечётно, x=2*x+1, иначе x=x/2. Ответ?", "11", "Сначала выбери ветку по условию.", "Для x=4 выбирается ветка иначе и получается 2."),
        _step("trace_transfer", "transfer", "s=0; для i от 1 до 4: s=s+i. Чему равен s?", "10", "Составь таблицу i,s.", "Для i от 1 до 3 сумма равна 6."),
        _step("trace_exam", "exam", "R=0. Для N=18: пока N>0, R=R+N%2; N=N//2. Чему равен R?", "2", "Алгоритм считает единицы двоичной записи.", "10₁₀=1010₂ содержит две единицы."),
        _step("trace_exam_transfer", "exam_transfer", "Тот же алгоритм применили к N=29. Чему равен R?", "4", "Выполни независимую трассировку.", "Проверяй N после каждого целочисленного деления."),
    ),
    "information.units_conversion": (
        _step("units_foundation", "foundation", "Сколько бит в одном байте?", "8", "1 байт = 8 бит.", "2 байта = 16 бит."),
        _step("units_basic", "basic", "Сколько байт в 4 Кбайт? Используй 1 Кбайт=1024 байта.", "4096", "Умножь число Кбайт на 1024.", "2 Кбайт = 2048 байт."),
        _step("units_intermediate", "intermediate", "Сколько бит в 3 Кбайт?", "24576", "Сначала переведи Кбайты в байты, затем в биты.", "1 Кбайт = 1024·8 = 8192 бит."),
        _step("units_transfer", "transfer", "Сколько Кбайт в 65536 бит?", "8", "Дели на 8, затем на 1024.", "16384 бит = 2 Кбайт."),
        _step("units_exam", "exam", "Файл содержит 2048 символов по 16 бит. Каков объём в Кбайтах?", "4", "Перемножь, переведи биты в байты и Кбайты.", "1024 символа по 8 бит занимают 1 Кбайт."),
        _step("units_exam_transfer", "exam_transfer", "Файл содержит 4096 символов по 12 бит. Каков объём в Кбайтах?", "6", "Реши новую вариацию независимо.", "Ответ должен учитывать 8 бит в байте и 1024 байта в Кбайте."),
    ),
}


@dataclass(frozen=True, slots=True)
class CourseItem:
    skill_id: str
    human_title: str
    reason: str
    evidence_summary: str
    related_exam_tasks: tuple[int, ...]
    prerequisites: tuple[str, ...]
    status: str
    estimated_steps: int
    next_action: str


def executable_skill_ids() -> frozenset[str]:
    # Task 14 remains the reference module in ege_learning_path.
    return frozenset(MODULE_STEPS) | {"number_systems.large_number_digits"}


def build_course(plan: Iterable[dict], states: dict | None = None) -> list[CourseItem]:
    """Deduplicate a diagnostic plan and order global prerequisites first."""
    skill_map = load_skill_map()
    states = states or {}
    requested: dict[str, list[dict]] = {}
    for row in plan:
        skill_id = row.get("skill_id")
        if get_skill(str(skill_id), skill_map):
            requested.setdefault(str(skill_id), []).append(row)
    ordered: list[str] = []
    for skill_id in requested:
        for candidate in prerequisite_path(skill_id, skill_map):
            if candidate not in ordered:
                ordered.append(candidate)
    result = []
    for skill_id in ordered:
        skill = get_skill(skill_id, skill_map)
        rows = requested.get(skill_id, [])
        tasks = set(skill.get("exam_tasks", []))
        tasks.update(int(row["task_number"]) for row in rows if row.get("task_number"))
        executable = skill_id in executable_skill_ids()
        mastered = bool(states.get(skill_id, {}).get("mastered"))
        unmet_prerequisites = [
            prerequisite
            for prerequisite in prerequisite_path(skill_id, skill_map)[:-1]
            if not states.get(prerequisite, {}).get("mastered")
        ]
        if mastered:
            status = "MASTERED"
            next_action = "Навык освоен"
        elif not executable:
            # Module readiness is independent of prerequisite readiness.  A
            # missing module is the actionable product limitation even when a
            # prerequisite is also unmet.
            status = "PENDING_MODULE"
            next_action = "Учебный модуль ещё не прошёл product gate"
        elif unmet_prerequisites:
            status = "BLOCKED_BY_PREREQUISITE"
            prerequisite_name = get_skill(unmet_prerequisites[0], skill_map)["name"]
            next_action = f"Сначала освоить «{prerequisite_name}»"
        else:
            status = "READY"
            next_action = "Начать foundation"
        result.append(CourseItem(
            skill_id=skill_id, human_title=skill["name"],
            reason="Пробел подтверждён диагностическими evidence",
            evidence_summary=f"Сигналов: {len(rows)}; контексты: " + ", ".join(f"№{n}" for n in sorted(tasks)),
            related_exam_tasks=tuple(sorted(tasks)), prerequisites=tuple(skill.get("prerequisites", [])),
            status=status, estimated_steps=6 if executable else 0,
            next_action=next_action,
        ))
    return result
