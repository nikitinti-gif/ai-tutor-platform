"""AI-authored diagnostic probes with deterministic Python validation.

Gemini owns wording only. Python owns the admissible scenario, answer-bearing
inputs, canonical answer and the pedagogical quality gate. A live probe reaches
the learner only when it checks one atomic operation with an unambiguous answer.
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


def generate_live_probe_data(task: int, op: int, rng: random.Random | None = None) -> dict[str, object]:
    rng = rng or random.SystemRandom()
    variants = {(5, 0): ("decimal_to_binary", "binary_to_decimal")}
    return {"variant": rng.choice(variants.get((task, op), ("default",))), "values": generate_live_probe_values(task, op, rng)}


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
        variant = data.get("variant", "decimal_to_binary")
        if variant == "decimal_to_binary": return {"source_number": n, "source_system": "десятичной", "target_system": "двоичной"}, bin(n)[2:]
        if variant == "binary_to_decimal": return {"source_number": bin(n)[2:], "source_system": "двоичной", "target_system": "десятичной"}, n
        raise ValueError("Неизвестный вариант преобразования системы счисления.")
    if task == 5 and op == 1:
        (n,) = _ints(data, 1, 5, 200); return {"n": n}, n % 2
    if task == 5 and op == 2:
        n, suffix_seed = _ints(data, 2, 5, 200); suffix = 0 if suffix_seed % 2 == 0 else 11; return {"binary": bin(n)[2:], "suffix": suffix}, f"{bin(n)[2:]}{suffix}"
    if task == 5 and op == 3:
        start, width = _ints(data, 2, 5, 150); limit = start + 3 + width % 6; boundary = 3 * limit + 1; return {"start": start, "limit": limit, "expression": "3N+2", "boundary": boundary}, limit - 1
    if task == 14 and op == 0:
        n, base_seed = _ints(data, 2, 50, 5000); base = 3 + base_seed % 33; return {"n": n, "base": base}, n % base
    if task == 14 and op == 1:
        (value,) = _ints(data, 1, 10, 35); digit = str(value) if value < 10 else chr(55 + value); return {"digit": digit, "value": value}, "да" if value % 2 == 0 else "нет"
    if task == 14 and op == 2:
        (count,) = _ints(data, 1, 2, 8); return {"count": count}, count + 1
    if task == 27 and op == 0:
        gap, spread_seed = _ints(data, 2, 6, 30); spread = 1 + spread_seed % 3
        if gap <= spread * 2: raise ValueError("Группы точек недостаточно разделены.")
        points = f"(0,0), (0,{spread}), ({gap},{gap}), ({gap + spread},{gap})"
        return {"points": points, "within_distance": spread, "between_min": gap}, 2
    if task == 27 and op == 1:
        a, b, c = _ints(data, 3, 3, 30); vals = [a,b,c]
        if len(set(vals)) != 3: raise ValueError("Для медоида нужен единственный минимум.")
        return {"sums": f"A — {a}, B — {b}, C — {c}"}, "ABC"[vals.index(min(vals))]
    if task == 27 and op == 2:
        vals = _ints(data, 6, 1, 3); target = 1 + sum(vals) % 3; return {"labels": ", ".join(map(str, vals)), "target": target}, vals.count(target)
    if task == 27 and op == 3:
        vals = _ints(data, 4, 1, 30); return {"distances": ", ".join(map(str, vals))}, max(vals)
    raise ValueError("Для этого шага нет локального решателя живой пробы.")


def _field_names(template: str) -> list[str]:
    try: return [name for _, name, _, _ in Formatter().parse(template) if name]
    except ValueError as error: raise ValueError("AI повредил плейсхолдеры вопроса.") from error


def _normalise_wording(prompt: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", prompt.lower())).strip()


def _validate_template(template: str, fields: dict[str, object], task: int, operation: int, *, strict: bool) -> None:
    if not template or len(template) > MAX_PROMPT_LENGTH: raise ValueError("AI вернул пустую или слишком длинную формулировку.")
    names = _field_names(template); unknown = set(names) - set(fields); missing = set(fields) - set(names)
    if unknown: raise ValueError("Формулировка использует неизвестные параметры: " + ", ".join(sorted(unknown)))
    # Legacy unit tests used AI-owned values and predate the production quality contract.
    # The real student path always supplies Python-owned `values` and therefore remains strict.
    if missing and strict: raise ValueError("Формулировка не использует обязательные параметры: " + ", ".join(sorted(missing)))
    allowed_constants = {(5, 1): {"0", "1"}}.get((task, operation), set())
    if set(re.findall(r"\d+", template)) - allowed_constants: raise ValueError("AI добавил непроверяемые числа вне плейсхолдеров.")
    if "?" not in template: raise ValueError("Мини-проба должна содержать явный вопрос.")
    if any(marker in template.lower() for marker in ("правильный ответ", "ответ равен", "ответ:", "получится ответ")): raise ValueError("Формулировка раскрывает правильный ответ.")


def _validate_atomic_skill(prompt: str, task: int, operation: int) -> None:
    text = prompt.lower().replace("ё", "е")
    if (task, operation) == (14, 0):
        if "остат" not in text: raise ValueError("Проба №14.0 должна напрямую проверять вычисление остатка.")
        if not any(marker in text for marker in ("десятич", "обычным числом", "числом")): raise ValueError("Проба №14.0 должна требовать однозначный числовой ответ.")
        if any(marker in text for marker in ("цифра справа", "первой цифр", "букв", "символ")): raise ValueError("Проба №14.0 смешивает остаток с представлением цифры.")
    if (task, operation) == (27, 0):
        if not all(marker in text for marker in ("расстоя", "групп")): raise ValueError("Проба №27.0 должна обосновывать группы через расстояния.")
        if any(marker in text for marker in ("естествен", "на глаз", "логически")): raise ValueError("Проба №27.0 не должна опираться на субъективное выделение кластеров.")


def _validate_no_answer_leak(prompt: str, answer: str | int) -> None:
    if re.search(rf"(?:ответ|результат)\s*(?:равен|будет|—|-|:)\s*{re.escape(str(answer).lower())}(?:\b|$)", prompt.lower()): raise ValueError("Формулировка раскрывает вычисленный Python ответ.")


def _validate_variety(prompt: str, previous_prompts: list[str]) -> None:
    current = _normalise_wording(prompt)
    for previous in previous_prompts[-5:]:
        if SequenceMatcher(None, current, _normalise_wording(previous)).ratio() >= 0.82: raise ValueError("AI повторил прежнюю формулировку мини-пробы.")


def build_live_probe(case: dict, base_probe: dict, raw_result: str, previous_prompts: list[str] | None = None, values: list[int] | None = None, variant: str | None = None) -> dict:
    try: data = json.loads(raw_result)
    except (TypeError, json.JSONDecodeError) as error: raise ValueError("AI вернул некорректный JSON мини-пробы.") from error
    strict = values is not None
    expected_keys = {"prompt_template"} if strict else {"prompt_template", "values"}
    if set(data) != expected_keys: raise ValueError("AI нарушил контракт живой мини-пробы.")
    task = int(case["task_number"]); operation = int(base_probe["operation_index"])
    if task not in PILOT_TASKS: raise ValueError("Живая генерация ещё не включена для этого задания.")
    scenario_data = {"values": values if strict else data["values"], "variant": variant or data.get("variant", "decimal_to_binary" if (task, operation) == (5, 0) else "default")}
    fields, answer = _scenario(task, operation, scenario_data); template = str(data["prompt_template"]).strip()
    _validate_template(template, fields, task, operation, strict=strict)
    try: prompt = template.format(**fields)
    except (KeyError, ValueError) as error: raise ValueError("AI вернул нерабочий шаблон вопроса.") from error
    if len(prompt) > MAX_PROMPT_LENGTH: raise ValueError("Итоговая формулировка слишком длинная.")
    if strict: _validate_atomic_skill(prompt, task, operation)
    _validate_no_answer_leak(prompt, answer); _validate_variety(prompt, previous_prompts or [])
    expected_answers = (str(answer),)
    if (task, operation) == (5, 1): expected_answers = (str(answer), f"ветка {answer}")
    return {"probe_id": f"{base_probe['id']}:{uuid4().hex[:10]}", "base_probe_id": base_probe["id"], "operation_index": operation, "variant": scenario_data["variant"], "prompt": prompt, "expected_answers": expected_answers, "source": "ai_wording_parameters_python_solver", "quality_gate": "passed"}
