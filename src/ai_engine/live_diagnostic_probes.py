"""AI-authored diagnostic probes with deterministic Python validation.

Gemini owns the wording and fresh inputs. Python owns the admissible scenario,
parameter validation, rendering and correct answer. Only validated probes reach
the learner; the static probe bank remains a failure-only fallback.
"""
from __future__ import annotations

from difflib import SequenceMatcher
import json
import random
import re
from string import Formatter
from uuid import uuid4


PILOT_TASKS = {5, 14, 27}
MAX_PROMPT_LENGTH = 500


def generate_live_probe_values(task: int, op: int, rng: random.Random | None = None) -> list[int]:
    """Create fresh solver inputs locally; the model never owns answer-bearing data."""
    rng = rng or random.SystemRandom()
    ranges = {
        (5, 0): ((10, 250),), (5, 1): ((5, 200),),
        (5, 2): ((5, 200), (5, 200)), (5, 3): ((5, 150), (5, 150)),
        (14, 0): ((50, 5000), (50, 5000)), (14, 1): ((10, 35),),
        (14, 2): ((2, 8),), (27, 0): ((12, 30), (6, 30)),
        (27, 1): ((3, 30), (3, 30), (3, 30)),
        (27, 2): ((1, 3),) * 6, (27, 3): ((1, 30),) * 4,
    }
    try:
        bounds = ranges[(task, op)]
    except KeyError as error:
        raise ValueError("Для этого шага нет генератора данных живой пробы.") from error
    for _ in range(20):
        values = [rng.randint(low, high) for low, high in bounds]
        try:
            _scenario(task, op, {"values": values})
            return values
        except ValueError:
            continue
    raise ValueError("Python не смог создать допустимые данные мини-пробы.")


def _ints(data: dict, count: int, low: int, high: int) -> list[int]:
    values = data.get("values")
    if not isinstance(values, list) or len(values) != count:
        raise ValueError("AI вернул неверное число параметров.")
    if any(type(value) is not int or not low <= value <= high for value in values):
        raise ValueError("Параметры AI выходят за безопасный диапазон.")
    return values


def _scenario(task: int, op: int, data: dict) -> tuple[dict[str, object], str | int]:
    if task == 5 and op == 0:
        (n,) = _ints(data, 1, 10, 250)
        return {"n": n}, bin(n)[2:]
    if task == 5 and op == 1:
        (n,) = _ints(data, 1, 5, 200)
        return {"n": n}, n % 2
    if task == 5 and op == 2:
        n, suffix_seed = _ints(data, 2, 5, 200)
        suffix = 0 if suffix_seed % 2 == 0 else 11
        return {"binary": bin(n)[2:], "suffix": suffix}, f"{bin(n)[2:]}{suffix}"
    if task == 5 and op == 3:
        start, width = _ints(data, 2, 5, 150)
        limit = start + 3 + width % 6
        boundary = 3 * limit + 1
        return {
            "start": start,
            "limit": limit,
            "expression": "3N+2",
            "boundary": boundary,
        }, limit - 1
    if task == 14 and op == 0:
        n, base_seed = _ints(data, 2, 50, 5000)
        base = 3 + base_seed % 33
        return {"n": n, "base": base}, n % base
    if task == 14 and op == 1:
        (value,) = _ints(data, 1, 10, 35)
        digit = str(value) if value < 10 else chr(55 + value)
        return {"digit": digit, "value": value}, "да" if value % 2 == 0 else "нет"
    if task == 14 and op == 2:
        (count,) = _ints(data, 1, 2, 8)
        return {"count": count}, count + 1
    if task == 27 and op == 0:
        gap, spread_seed = _ints(data, 2, 6, 30)
        spread = 1 + spread_seed % 3
        if gap <= spread * 2:
            raise ValueError("Группы точек недостаточно разделены.")
        points = f"(0,0), (0,{spread}), ({gap},{gap}), ({gap + spread},{gap})"
        return {"points": points}, 2
    if task == 27 and op == 1:
        a, b, c = _ints(data, 3, 3, 30)
        values = [a, b, c]
        if len(set(values)) != 3:
            raise ValueError("Для медоида нужен единственный минимум.")
        return {"a": a, "b": b, "c": c}, "ABC"[values.index(min(values))]
    if task == 27 and op == 2:
        values = _ints(data, 6, 1, 3)
        target = 1 + sum(values) % 3
        return {"labels": ", ".join(map(str, values)), "target": target}, values.count(target)
    if task == 27 and op == 3:
        values = _ints(data, 4, 1, 30)
        return {"distances": ", ".join(map(str, values))}, max(values)
    raise ValueError("Для этого шага нет локального решателя живой пробы.")


def _field_names(template: str) -> list[str]:
    try:
        return [name for _, name, _, _ in Formatter().parse(template) if name]
    except ValueError as error:
        raise ValueError("AI повредил плейсхолдеры вопроса.") from error


def _normalise_wording(prompt: str) -> str:
    prompt = re.sub(r"\d+", "#", prompt.lower())
    return re.sub(r"\s+", " ", prompt).strip()


def _validate_template(
    template: str,
    fields: dict[str, object],
    task: int,
    operation: int,
) -> None:
    if not template or len(template) > MAX_PROMPT_LENGTH:
        raise ValueError("AI вернул пустую или слишком длинную формулировку.")
    names = _field_names(template)
    if set(names) != set(fields) or any(names.count(name) != 1 for name in names):
        raise ValueError("Формулировка должна использовать каждый разрешённый параметр ровно один раз.")
    allowed_constants = {
        # The base is part of the skill definition, not answer-bearing input.
        # Gemini naturally writes either "binary" or "base 2".
        (5, 0): {"2"},
    }.get((task, operation), set())
    numeric_literals = set(re.findall(r"\d+", template))
    if numeric_literals - allowed_constants:
        raise ValueError("AI добавил непроверяемые числа вне плейсхолдеров.")
    if "?" not in template:
        raise ValueError("Мини-проба должна содержать явный вопрос.")
    lowered = template.lower()
    if any(marker in lowered for marker in ("правильный ответ", "ответ равен", "ответ:", "получится ответ")):
        raise ValueError("Формулировка раскрывает правильный ответ.")


def _validate_intent(task: int, op: int, prompt: str) -> None:
    """Reject fluent questions that test a different operation."""
    requirements = {
        (5, 0): (("двоич",), ("перев", "запис")),
        (5, 1): (("последн",), ("бит", "цифр"), ("ветк",)),
        # Gemini often describes appending a suffix as extending or completing
        # a binary string.  Requiring the literal direction "справа" rejected
        # valid questions even though the suffix operation was unambiguous.
        (5, 2): (
            ("допис", "присоедин", "добав", "припис", "продолж", "дополн"),
            ("двоич", "строк", "запис", "последователь", "результ"),
        ),
        (5, 3): (("наибольш", "максим"), ("неравен", "услов")),
        (14, 0): (("остат",), ("дел",)),
        (14, 1): (("чётн", "четн"),),
        (14, 2): (("остат",), ("частн",), ("цифр", "разряд")),
        (27, 0): (("кластер", "групп"),),
        (27, 1): (("медоид",), ("сумм",)),
        (27, 2): (("метк",), ("сколько", "количеств")),
        (27, 3): (("расстоян",), ("максим", "наибольш")),
    }
    lowered = prompt.lower()
    if any(not any(word in lowered for word in alternatives) for alternatives in requirements[(task, op)]):
        raise ValueError("Формулировка не проверяет выбранный диагностический шаг.")


def _validate_no_answer_leak(prompt: str, answer: str | int) -> None:
    escaped = re.escape(str(answer).lower())
    pattern = rf"(?:ответ|результат)\s*(?:равен|будет|—|-|:)\s*{escaped}(?:\b|$)"
    if re.search(pattern, prompt.lower()):
        raise ValueError("Формулировка раскрывает вычисленный Python ответ.")


def _validate_variety(prompt: str, previous_prompts: list[str]) -> None:
    current = _normalise_wording(prompt)
    for previous in previous_prompts[-5:]:
        ratio = SequenceMatcher(None, current, _normalise_wording(previous)).ratio()
        if ratio >= 0.82:
            raise ValueError("AI повторил прежнюю формулировку мини-пробы.")


def build_live_probe(
    case: dict,
    base_probe: dict,
    raw_result: str,
    previous_prompts: list[str] | None = None,
    values: list[int] | None = None,
) -> dict:
    """Validate AI wording and parameters, then solve the probe in Python."""
    try:
        data = json.loads(raw_result)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError("AI вернул некорректный JSON мини-пробы.") from error
    expected_keys = {"prompt_template"} if values is not None else {"prompt_template", "values"}
    if set(data) != expected_keys:
        raise ValueError("AI нарушил контракт живой мини-пробы.")

    task = int(case["task_number"])
    operation = int(base_probe["operation_index"])
    if task not in PILOT_TASKS:
        raise ValueError("Живая генерация ещё не включена для этого задания.")

    fields, answer = _scenario(task, operation, {"values": values if values is not None else data["values"]})
    template = str(data["prompt_template"]).strip()
    _validate_template(template, fields, task, operation)
    try:
        prompt = template.format(**fields)
    except (KeyError, ValueError) as error:
        raise ValueError("AI вернул нерабочий шаблон вопроса.") from error
    if len(prompt) > MAX_PROMPT_LENGTH:
        raise ValueError("Итоговая формулировка слишком длинная.")
    _validate_intent(task, operation, prompt)
    _validate_no_answer_leak(prompt, answer)
    _validate_variety(prompt, previous_prompts or [])

    return {
        "probe_id": f"{base_probe['id']}:{uuid4().hex[:10]}",
        "base_probe_id": base_probe["id"],
        "operation_index": operation,
        "prompt": prompt,
        "expected_answers": (str(answer),),
        "source": "ai_wording_parameters_python_solver",
    }
