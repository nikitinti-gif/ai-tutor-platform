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


def _module(kind: str, rows: tuple[tuple[str, str, str, str], ...]) -> tuple[dict, ...]:
    """Build a six-checkpoint module without executing learner supplied code."""
    steps = []
    for difficulty, prompt, answer, support in rows:
        item = _step(f"{kind}_{difficulty}", difficulty, prompt, answer, support,
                     "Сначала проверь ход решения на меньшем примере.")
        item["step_type"] = kind
        steps.append(item)
    return tuple(steps)


# These modules are global skills, not copies per exam number.  Programming
# checkpoints ask about algorithm and code behaviour; application checkpoints
# explicitly use tabular/file-shaped data.  No arbitrary learner code is run.
MODULE_STEPS.update({
    "algorithms.recursion": _module("reasoning", (
        ("foundation", "F(0)=2, F(n)=F(n-1)+3. Чему равно F(1)?", "5", "Начни с базового случая."),
        ("basic", "F(0)=1, F(n)=2*F(n-1). Чему равно F(3)?", "8", "Последовательно вычисли F(1), F(2), F(3)."),
        ("intermediate", "Сколько всего вызовов сделает F(3), если F(0) завершается, а F(n) вызывает F(n-1) один раз?", "4", "Посчитай и исходный вызов, и базовый."),
        ("transfer", "G(1)=1, G(n)=G(n-1)+n. Чему равно G(4)?", "10", "Разверни цепочку до G(1)."),
        ("exam", "F(1)=1; F(n)=n*F(n-1). Найди F(6)/F(4).", "30", "Сократи общую рекурсивную часть."),
        ("exam_transfer", "F(0)=0; F(n)=F(n-1)+2*n. Найди F(5).", "30", "Новая функция: реши независимо."),
    )),
    "algorithms.dynamic_programming": _module("reasoning", (
        ("foundation", "В DP для числа способов дойти до клетки i шагами 1 или 2 какое состояние достаточно хранить? Ответ: ways[i] или i.", "ways[i]", "Состояние хранит ответ подзадачи."),
        ("basic", "ways[0]=1, ways[1]=1, ways[i]=ways[i-1]+ways[i-2]. Чему равно ways[4]?", "5", "Заполняй состояния слева направо."),
        ("intermediate", "cost[0]=0; cost[i]=min(cost[i-1]+2,cost[i-2]+3). Чему равно cost[4]?", "6", "Для каждого i сравни оба перехода."),
        ("transfer", "ways[0]=1; разрешены шаги 1 и 3. Сколько способов попасть в 5?", "4", "Переход: ways[i]=ways[i-1]+ways[i-3]."),
        ("exam", "Исполнитель прибавляет 1 или умножает на 2. Сколько программ переводят 1 в 6, не заходя в 4?", "2", "Состояние — число программ до значения; запрещённому состоянию дай 0."),
        ("exam_transfer", "Исполнитель прибавляет 1 или 2. Сколько программ переводят 2 в 7 и проходят через 5?", "6", "Перемножь независимые количества путей 2→5 и 5→7."),
    )),
    "algorithms.game_strategy": _module("reasoning", (
        ("foundation", "За ход к куче можно прибавить 1. Победа при >=5. Позиция 4 выигрышная? Ответ да/нет.", "да", "Есть ход сразу в терминальную позицию."),
        ("basic", "Ходы +1 или *2, победа при >=10. Назови минимальную выигрышную за один ход позицию.", "5", "Проверь возможность удвоения."),
        ("intermediate", "Если все ходы из позиции ведут в выигрышные за один ход позиции соперника, позиция выигрышная или проигрышная?", "проигрышная", "После любого хода соперник завершит игру."),
        ("transfer", "Ходы +1 или *2, победа при >=12. Минимальная позиция W1?", "6", "W1 имеет хотя бы один ход в терминал."),
        ("exam", "Ходы +1 или *2, победа при >=20. Каков минимальный S, из которого Петя выигрывает первым ходом?", "10", "Это классификация W1 для №19–21."),
        ("exam_transfer", "Ходы +1 или *3, победа при >=25. Каков минимальный S для победы первым ходом?", "9", "Независимо проверь оба разрешённых хода."),
    )),
    "programming.strings": _module("programming", (
        ("foundation", "Что вернёт len('КЕГЭ')?", "4", "Строка — последовательность символов."),
        ("basic", "Какой срез Python получает первые 3 символа строки s?", "s[:3]", "Правая граница среза не включается."),
        ("intermediate", "Чему равно 'ABA'.count('A')?", "2", "count считает неперекрывающиеся вхождения."),
        ("transfer", "Что выведет ''.join(ch for ch in 'A1B2' if ch.isdigit())?", "12", "Отфильтруй только цифры."),
        ("exam", "После замен 01→2 в строке 0101 до исчезновения 01 какая строка получится?", "22", "Применяй замену слева до остановки."),
        ("exam_transfer", "Сколько строк длины 3 над A,B содержат ровно две A?", "3", "Это независимый алгоритмический checkpoint: выбери позиции A."),
    )),
    "programming.sequences": _module("programming", (
        ("foundation", "Что вернёт sum([2,3,5])?", "10", "Агрегат sum складывает элементы."),
        ("basic", "Что выведет [x for x in [1,2,3,4] if x%2==0]?", "[2, 4]", "Условие оставляет чётные элементы."),
        ("intermediate", "Для a=[4,1,7] чему равно max(a)-min(a)?", "6", "Нужны оба экстремума."),
        ("transfer", "Сколько соседних пар с возрастающим порядком в [1,3,2,5]?", "2", "Сравни a[i] с a[i+1]."),
        ("exam", "Сколько пар чисел в [2,7,4,9], сумма которых нечётна?", "4", "Нечётная сумма получается из разных чётностей."),
        ("exam_transfer", "Сколько соседних пар в [5,2,8,3,7] имеют сумму >9?", "2", "Проверь каждое соседнее окно независимо."),
    )),
    "programming.masks": _module("programming", (
        ("foundation", "Соответствует ли 1234 маске 12*? Ответ да/нет.", "да", "* означает любую последовательность."),
        ("basic", "Соответствует ли 507 маске 5?7? Ответ да/нет.", "да", "? означает ровно один символ."),
        ("intermediate", "Какой оператор Python проверяет остаток деления n на 17?", "n % 17", "Используй оператор %."),
        ("transfer", "Сколько четырёхзначных чисел соответствует маске 12??", "100", "Каждый ? имеет десять вариантов."),
        ("exam", "Минимальное число вида 3?5, делящееся на 5.", "305", "Последняя цифра уже задаёт делимость; минимизируй ?."),
        ("exam_transfer", "Минимальное число вида 4?2, делящееся на 3.", "402", "Сумма цифр должна делиться на 3."),
    )),
    "programming.grouping": _module("programming", (
        ("foundation", "Какой ключ группировки у записи ('A', 7), если группа задаётся первым полем?", "A", "Ключ — выбранное поле записи."),
        ("basic", "Сколько групп после группировки A,A,B,C,C по букве?", "3", "Считай уникальные ключи."),
        ("intermediate", "После сортировки [(2,5),(1,9),(2,3)] по (первое, второе) какая запись первая?", "(1, 9)", "Кортежи сравниваются слева направо."),
        ("transfer", "Максимум значений по группе A в записях A:2,B:9,A:7?", "7", "Сначала отфильтруй группу."),
        ("exam", "В группах A:[3,8], B:[5,6] найди сумму максимумов.", "14", "Агрегируй внутри каждой группы."),
        ("exam_transfer", "В группах X:[2,9,4], Y:[7,1] найди сумму минимумов.", "3", "Новая агрегация на независимых данных."),
    )),
})


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
    estimated_time_minutes: int
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
        if get_skill(str(skill_id), skill_map) and not states.get(skill_id, {}).get("mastered"):
            requested.setdefault(str(skill_id), []).append(row)
    ordered: list[str] = []
    # Include unmet prerequisites even when the diagnostic plan did not repeat
    # them.  This closes real knowledge gaps rather than jumping over them.
    for skill_id in tuple(requested):
        for prerequisite in prerequisite_path(skill_id, skill_map)[:-1]:
            if not states.get(prerequisite, {}).get("mastered"):
                requested.setdefault(prerequisite, [{"prerequisite_for": skill_id}])
    for skill_id in requested:
        for candidate in prerequisite_path(skill_id, skill_map):
            if candidate in requested and candidate not in ordered:
                ordered.append(candidate)
    result = []
    for skill_id in ordered:
        skill = get_skill(skill_id, skill_map)
        rows = requested[skill_id]
        tasks = set(skill.get("exam_tasks", []))
        tasks.update(int(row["task_number"]) for row in rows if row.get("task_number"))
        executable = skill_id in executable_skill_ids()
        unmet = [p for p in skill.get("prerequisites", []) if not states.get(p, {}).get("mastered")]
        # The task-14 reference path embeds its base-conversion prerequisite as
        # an explicit checkpoint and therefore remains restart-compatible.
        available = executable and (not unmet or skill_id == "number_systems.large_number_digits")
        result.append(CourseItem(
            skill_id=skill_id, human_title=skill["name"],
            reason="Пробел подтверждён диагностическими evidence",
            evidence_summary=f"Сигналов: {len(rows)}; контексты: " + ", ".join(f"№{n}" for n in sorted(tasks)),
            related_exam_tasks=tuple(sorted(tasks)), prerequisites=tuple(skill.get("prerequisites", [])),
            status="READY" if available else "PENDING", estimated_steps=6 if executable else 0,
            estimated_time_minutes=15 if executable else 0,
            next_action=("Начать foundation" if available else
                         ("Сначала освоить: " + ", ".join(unmet) if unmet else
                          "Учебный модуль ещё не прошёл product gate")),
        ))
    return result
