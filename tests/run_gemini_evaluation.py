import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ai_engine.homework_checker import check_homework_text


CASES = [
    {
        "id": "conditions_correct",
        "topic": "Условный оператор Python",
        "task": "Дано целое число. Вывести 'YES', если оно положительное, иначе вывести 'NO'.",
        "solution": "n = int(input())\nif n > 0:\n    print('YES')\nelse:\n    print('NO')",
        "expected": "correct",
    },
    {
        "id": "conditions_error_zero",
        "topic": "Условный оператор Python",
        "task": "Дано целое число. Вывести 'YES', если оно неотрицательное, иначе вывести 'NO'.",
        "solution": "n = int(input())\nif n > 0:\n    print('YES')\nelse:\n    print('NO')",
        "expected": "has_error",
    },
    {
        "id": "loop_correct",
        "topic": "Циклы Python",
        "task": "Вывести целые числа от 1 до 10 включительно, каждое с новой строки.",
        "solution": "for i in range(1, 11):\n    print(i)",
        "expected": "correct",
    },
    {
        "id": "loop_off_by_one",
        "topic": "Циклы Python",
        "task": "Вывести целые числа от 1 до 10 включительно, каждое с новой строки.",
        "solution": "for i in range(1, 10):\n    print(i)",
        "expected": "has_error",
    },
    {
        "id": "sum_correct",
        "topic": "Алгоритмы с накоплением суммы",
        "task": "Вводятся три целых числа. Вывести их сумму.",
        "solution": "a = int(input())\nb = int(input())\nc = int(input())\nprint(a + b + c)",
        "expected": "correct",
    },
    {
        "id": "sum_error_product",
        "topic": "Алгоритмы с накоплением суммы",
        "task": "Вводятся три целых числа. Вывести их сумму.",
        "solution": "a = int(input())\nb = int(input())\nc = int(input())\nprint(a * b * c)",
        "expected": "has_error",
    },
    {
        "id": "string_length_correct",
        "topic": "Строки Python",
        "task": "Вводится строка. Вывести количество символов в ней.",
        "solution": "s = input()\nprint(len(s))",
        "expected": "correct",
    },
    {
        "id": "index_error",
        "topic": "Индексация строк",
        "task": "Вводится непустая строка. Вывести её первый символ.",
        "solution": "s = input()\nprint(s[1])",
        "expected": "has_error",
    },
    {
        "id": "binary_correct",
        "topic": "Системы счисления",
        "task": "Перевести двоичное число 10110 в десятичную систему.",
        "solution": "10110₂ = 16 + 4 + 2 = 22₁₀",
        "expected": "correct",
    },
    {
        "id": "binary_error",
        "topic": "Системы счисления",
        "task": "Перевести двоичное число 10110 в десятичную систему.",
        "solution": "10110₂ = 16 + 8 + 2 = 26₁₀",
        "expected": "has_error",
    },
    {
        "id": "logic_correct",
        "topic": "Логические выражения",
        "task": "Вычислить значение выражения НЕ(1 И 0) ИЛИ 0.",
        "solution": "1 И 0 = 0; НЕ 0 = 1; 1 ИЛИ 0 = 1. Ответ: 1.",
        "expected": "correct",
    },
    {
        "id": "logic_error",
        "topic": "Логические выражения",
        "task": "Вычислить значение выражения НЕ(1 И 0) ИЛИ 0.",
        "solution": "1 И 0 = 1; НЕ 1 = 0; 0 ИЛИ 0 = 0. Ответ: 0.",
        "expected": "has_error",
    },
    {
        "id": "information_volume_correct",
        "topic": "Измерение информации",
        "task": "Файл имеет размер 2 Кбайт. Сколько это байт? Использовать 1 Кбайт = 1024 байта.",
        "solution": "2 * 1024 = 2048 байт.",
        "expected": "correct",
    },
    {
        "id": "information_volume_error",
        "topic": "Измерение информации",
        "task": "Файл имеет размер 2 Кбайт. Сколько это байт? Использовать 1 Кбайт = 1024 байта.",
        "solution": "2 * 1000 = 2000 байт.",
        "expected": "has_error",
    },
    {
        "id": "unclear_solution",
        "topic": "Алгоритмы",
        "task": "Вводится число. Вывести его квадрат.",
        "solution": "Я примерно понял, но не знаю, что написать.",
        "expected": "unclear",
    },
]


def main():
    matched = 0
    failed = 0

    for index, case in enumerate(CASES, start=1):
        print(f"\n[{index}/{len(CASES)}] {case['id']}")

        try:
            result = check_homework_text(
                text=case["solution"],
                task_text=case["task"],
                topic=case["topic"],
                synthetic_test=True,
            )
        except Exception as error:
            failed += 1
            print(f"API ERROR: {type(error).__name__}: {error}")
            time.sleep(2)
            continue

        actual = result["status"]
        is_match = actual == case["expected"]
        matched += int(is_match)

        print(
            json.dumps(
                {
                    "expected": case["expected"],
                    "actual": actual,
                    "match": is_match,
                    "confidence": result["confidence"],
                    "feedback": result["feedback"],
                    "hint": result["hint"],
                    "error_type": result["error_type"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        time.sleep(2)

    print("\n=== SUMMARY ===")
    print(f"Cases: {len(CASES)}")
    print(f"Matched expected status: {matched}")
    print(f"API errors: {failed}")


if __name__ == "__main__":
    main()
