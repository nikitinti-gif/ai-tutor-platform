"""Validated live diagnostic probes for the 5/14/27 pilot.

The model supplies fresh parameters.  Python owns rendering and the answer,
so an attractive but mathematically invalid model response never reaches a
student.
"""
from __future__ import annotations

import json
from uuid import uuid4


PILOT_TASKS = {5, 14, 27}


def _ints(data: dict, count: int, low: int, high: int) -> list[int]:
    values = data.get("values")
    if not isinstance(values, list) or len(values) != count:
        raise ValueError("AI вернул неверное число параметров.")
    if any(type(value) is not int or not low <= value <= high for value in values):
        raise ValueError("Параметры AI выходят за безопасный диапазон.")
    return values


def build_live_probe(case: dict, base_probe: dict, raw_result: str) -> dict:
    """Turn model parameters into a locally solved, quality-checked probe."""
    try:
        data = json.loads(raw_result)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("AI вернул некорректный JSON параметров.") from error
    task = int(case["task_number"])
    operation = int(base_probe["operation_index"])
    if task not in PILOT_TASKS:
        raise ValueError("Живая генерация ещё не включена для этого задания.")

    prompt, answer = _render(task, operation, data)
    if not prompt or len(prompt) > 500:
        raise ValueError("Сгенерированная проба не прошла фильтр качества.")
    return {
        "probe_id": f"{base_probe['id']}:{uuid4().hex[:10]}",
        "base_probe_id": base_probe["id"],
        "operation_index": operation,
        "prompt": prompt,
        "expected_answers": (str(answer),),
        "source": "ai_parameters_python_solver",
    }


def _render(task: int, op: int, data: dict) -> tuple[str, str | int]:
    if task == 5 and op == 0:
        (n,) = _ints(data, 1, 10, 250)
        return f"Переведите десятичное число {n} в двоичную систему. Запишите только результат.", bin(n)[2:]
    if task == 5 and op == 1:
        n, bit = _ints(data, 2, 5, 200)
        bit %= 2
        return (f"Алгоритм проверяет последний бит числа {n}. Если он равен 1, выбирается ветка 1, иначе ветка 0. Какую ветку выберет алгоритм?", n % 2)
    if task == 5 and op == 2:
        n, suffix = _ints(data, 2, 5, 200)
        suffix = 0 if suffix % 2 == 0 else 11
        return f"Двоичная запись числа {n} равна {bin(n)[2:]}. Допишите справа {suffix}. Запишите итоговую строку.", f"{bin(n)[2:]}{suffix}"
    if task == 5 and op == 3:
        start, width = _ints(data, 2, 5, 150)
        width = 3 + width % 6
        limit = start + width
        return f"Проверьте целые N от {start} до {limit}: условие 3N+2 < {3*limit+1}. Найдите наибольшее подходящее N.", limit - 1
    if task == 14 and op == 0:
        n, base = _ints(data, 2, 50, 5000)
        base = 3 + base % 33
        return f"Какой остаток получится при первом делении числа {n} на {base} при переводе в систему с основанием {base}?", n % base
    if task == 14 and op == 1:
        (value,) = _ints(data, 1, 10, 35)
        digit = str(value) if value < 10 else chr(55 + value)
        return f"Цифра {digit} имеет числовое значение {value}. Является ли это значение чётным? Ответьте да или нет.", "да" if value % 2 == 0 else "нет"
    if task == 14 and op == 2:
        (count,) = _ints(data, 1, 2, 8)
        return f"При последовательном делении получено {count} остатков, затем осталось ненулевое частное. Сколько цифр будет в итоговой записи?", count + 1
    if task == 27 and op == 0:
        gap, spread = _ints(data, 2, 4, 30)
        spread = 1 + spread % 3
        return f"Точки (0,0), (0,{spread}), ({gap},{gap}), ({gap+spread},{gap}) образуют хорошо разделённые группы. Сколько естественных кластеров видно?", 2
    if task == 27 and op == 1:
        a, b, c = _ints(data, 3, 3, 30)
        values = [a, b, c]
        if len(set(values)) != 3:
            raise ValueError("Для медоида нужен единственный минимум.")
        labels = "ABC"
        return f"Суммы расстояний до остальных точек: A — {a}, B — {b}, C — {c}. Какая точка является медоидом?", labels[values.index(min(values))]
    if task == 27 and op == 2:
        values = _ints(data, 6, 1, 3)
        target = 1 + sum(values) % 3
        return f"Метки кластеров: {', '.join(map(str, values))}. Сколько точек имеет метку {target}?", values.count(target)
    if task == 27 and op == 3:
        values = _ints(data, 4, 1, 30)
        return f"Расстояния от медоида до точек равны {', '.join(map(str, values))}. Найдите максимальное расстояние.", max(values)
    raise ValueError("Для этого шага нет локального решателя живой пробы.")
