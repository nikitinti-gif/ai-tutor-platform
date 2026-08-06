"""Official FIPI open KЕГЭ informatics variant 2026 answer configuration.

The question text is stored in the project PDF (ИНФ.pdf). This module contains
only structured metadata needed by the Telegram exam flow and local answer
verification. No LLM/API call is required to check any of the 27 final answers.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EgeTask:
    number: int
    title: str
    answer_rows: tuple[tuple[str, ...], ...]
    attachment_required: bool = False
    prompt: str = "Введите итоговый ответ в формате КЕГЭ."


# Answer key independently published for the official FIPI open variant.
# Multiple output rows are preserved for tasks 25 and 27.
OPEN_VARIANT_2026: dict[int, EgeTask] = {
    1: EgeTask(1, "Граф и таблица дорог", (("9",),)),
    2: EgeTask(2, "Таблица истинности", (("yxwz",),), prompt="Введите четыре буквы подряд без пробелов."),
    3: EgeTask(3, "Реляционная база данных", (("445",),), True),
    4: EgeTask(4, "Условие Фано", (("1000",),)),
    5: EgeTask(5, "Анализ алгоритма над двоичной записью", (("12",),)),
    6: EgeTask(6, "Исполнитель Черепаха", (("261",),)),
    7: EgeTask(7, "Кодирование звука", (("7656",),)),
    8: EgeTask(8, "Комбинаторика слов", (("7903",),)),
    9: EgeTask(9, "Электронная таблица", (("2354",),), True),
    10: EgeTask(10, "Поиск в текстовом документе", (("115",),), True),
    11: EgeTask(11, "Кодирование идентификаторов", (("3344",),)),
    12: EgeTask(12, "Машина Тьюринга", (("1024",),)),
    13: EgeTask(13, "IP-адрес и маска сети", (("780",),)),
    14: EgeTask(14, "Системы счисления", (("1013",),)),
    15: EgeTask(15, "Логика отрезков", (("28",),)),
    16: EgeTask(16, "Рекурсивная функция", (("1431",),)),
    17: EgeTask(17, "Пары последовательности", (("5001", "962"),), True, "Введите два числа через пробел."),
    18: EgeTask(18, "Робот в электронной таблице", (("2476", "436"),), True, "Введите максимум и минимум через пробел."),
    19: EgeTask(19, "Теория игр: один ход", (("16",),)),
    20: EgeTask(20, "Теория игр: два значения", (("39", "40"),), prompt="Введите два числа по возрастанию через пробел."),
    21: EgeTask(21, "Теория игр: выигрышная стратегия", (("41",),)),
    22: EgeTask(22, "Параллельные процессы", (("34",),), True),
    23: EgeTask(23, "Количество программ исполнителя", (("188",),)),
    24: EgeTask(24, "Обработка строки", (("2287",),), True),
    25: EgeTask(
        25,
        "Маска числа и делимость",
        (
            ("8901677598", "901527"),
            ("8905627198", "901927"),
            ("8912617990", "902635"),
            ("8941667298", "905577"),
            ("8952607690", "906685"),
            ("8970607992", "908508"),
            ("8988647790", "910335"),
        ),
        prompt="Введите семь строк по два числа в каждой, сохраняя порядок.",
    ),
    26: EgeTask(26, "Обработка товаров", (("42300", "11"),), True, "Введите два числа через пробел."),
    27: EgeTask(
        27,
        "Кластеризация и геометрия",
        (("44694", "69754"), ("138716", "34029")),
        True,
        "Введите две строки по два числа в каждой.",
    ),
}


def get_open_variant_task(number: int) -> EgeTask:
    try:
        return OPEN_VARIANT_2026[number]
    except KeyError as exc:
        raise ValueError("Номер задания должен быть от 1 до 27.") from exc


def validate_open_variant() -> None:
    expected = set(range(1, 28))
    actual = set(OPEN_VARIANT_2026)
    if actual != expected:
        raise RuntimeError(f"Некорректный вариант: missing={expected-actual}, extra={actual-expected}")
    for number, task in OPEN_VARIANT_2026.items():
        if task.number != number or not task.answer_rows:
            raise RuntimeError(f"Некорректная конфигурация задания {number}")
        if any(not row or any(not value.strip() for value in row) for row in task.answer_rows):
            raise RuntimeError(f"Пустой эталон в задании {number}")


validate_open_variant()
