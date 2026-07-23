from src.ai_engine.parser import (
    parse_homework_check_response,
    parse_image_transcription_response,
)
from src.ai_engine.llm_client import LLMClient
from src.ai_engine.provider_clients import create_text_provider
from src.ai_engine.schemas import enforce_error_evidence
from src.ai_engine.schemas import validate_diagnostic_level_result
import json
import os
import re


RECHECK_CONFIDENCE_THRESHOLD = float(
    os.getenv("GEMINI_RECHECK_CONFIDENCE_THRESHOLD", "1.0")
)


def check_homework_text(
    text: str,
    task_text: str | None = None,
    topic: str | None = None,
    synthetic_test: bool = False,
    provider_name: str = "gemini",
) -> dict:
    if not synthetic_test:
        return {
            "status": "unclear",
            "confidence": 0.0,
            "feedback": (
                "Реальная AI-проверка пока тестируется только "
                "на искусственных примерах."
            ),
            "hint": "Дождись проверки преподавателя.",
            "error_type": None,
            "topic": topic,
            "needs_teacher_review": True,
        }

    client = create_text_provider(provider_name)

    raw_response = client.check_homework_text(
        text=text,
        task_text=task_text,
        topic=topic,
        synthetic_test=True,
    )
    result = parse_homework_check_response(raw_response)
    result = enforce_error_evidence(result, text)
    if provider_name == "gemini" and _needs_critical_recheck(result):
        second_raw = client.critically_recheck_homework(
            text=text,
            task_text=task_text,
            topic=topic,
            first_result=json.dumps(result, ensure_ascii=False),
            synthetic_test=True,
        )
        second = enforce_error_evidence(
            parse_homework_check_response(second_raw),
            text,
        )
        result = _reconcile_homework_checks(result, second)
    return result


def check_homework_image(
    image_bytes: bytes,
    mime_type: str,
    task_text: str | None = None,
    topic: str | None = None,
    synthetic_test: bool = False,
    provider_name: str = "gemini",
    pilot_v2: bool = False,
) -> dict:
    pilot_allowed = pilot_v2 and provider_name == "qwen"
    if not synthetic_test and not pilot_allowed:
        return {
            "status": "unclear",
            "confidence": 0.0,
            "feedback": (
                "Проверка реальных фотографий пока не подключена."
            ),
            "hint": "Дождись проверки преподавателя.",
            "error_type": None,
            "topic": topic,
            "needs_teacher_review": True,
        }

    if provider_name == "gemini":
        client = LLMClient()
    else:
        client = create_text_provider(provider_name)
        if not hasattr(client, "transcribe_homework_image"):
            raise ValueError(
                f"Провайдер {provider_name} не поддерживает изображения."
            )
    transcription_kwargs = {
        "image_bytes": image_bytes,
        "mime_type": mime_type,
        "synthetic_test": synthetic_test,
    }
    if pilot_allowed:
        transcription_kwargs["pilot_v2"] = True
    raw_transcription = client.transcribe_homework_image(
        **transcription_kwargs
    )
    transcription = parse_image_transcription_response(raw_transcription)

    if transcription["legibility"] != "readable":
        return {
            "status": "unclear",
            "confidence": transcription["confidence"],
            "feedback": (
                "Изображение недостаточно читаемо для надёжной проверки."
            ),
            "hint": (
                "Сделай новое фото без размытия, чтобы всё решение "
                "и отступы были видны."
            ),
            "error_type": "unreadable_image",
            "topic": topic,
            "needs_teacher_review": True,
            "image_legibility": transcription["legibility"],
            "image_transcription": transcription["transcription"],
        }

    check_kwargs = {
        "text": transcription["transcription"],
        "task_text": task_text,
        "topic": topic,
        "synthetic_test": synthetic_test,
    }
    if pilot_allowed:
        check_kwargs["pilot_v2"] = True
    raw_response = client.check_homework_text(**check_kwargs)
    result = parse_homework_check_response(raw_response)
    result = enforce_error_evidence(result, transcription["transcription"])
    if provider_name == "gemini" and _needs_critical_recheck(result):
        second_raw = client.critically_recheck_homework(
            text=transcription["transcription"],
            task_text=task_text,
            topic=topic,
            first_result=json.dumps(result, ensure_ascii=False),
            synthetic_test=synthetic_test,
        )
        second = enforce_error_evidence(
            parse_homework_check_response(second_raw),
            transcription["transcription"],
        )
        result = _reconcile_homework_checks(result, second)
    result["image_legibility"] = transcription["legibility"]
    result["image_transcription"] = transcription["transcription"]

    return result


def render_check_result_for_student(result: dict) -> str:
    if result["status"] == "correct":
        return (
            "✅ Решение принято!\n\n"
            f"{result['feedback']}\n\n"
            f"💡 {result['hint']}"
        )

    if result["status"] == "has_error":
        return (
            "🟡 Нашёл место, которое нужно перепроверить.\n\n"
            f"{result['feedback']}\n\n"
            f"❓ Подсказка: {result['hint']}"
        )

    return (
        "🔴 Нужна проверка преподавателя.\n\n"
        f"{result['feedback']}\n\n"
        f"💡 {result['hint']}"
    )


def check_diagnostic_transcription(*, student_solution: str, topic: str, tasks: list[dict], synthetic_test: bool = False) -> dict:
    client = LLMClient()
    raw = client.check_diagnostic_levels(
        topic=topic, tasks=tasks, student_solution=student_solution,
        synthetic_test=synthetic_test,
    )
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        data = {}
    data = _apply_diagnostic_semantic_guards(
        data=data,
        tasks=tasks,
        student_solution=student_solution,
    )
    first_validated = validate_diagnostic_level_result(data, topic)
    if _needs_diagnostic_recheck(first_validated):
        second_raw = client.critically_recheck_diagnostic(
            topic=topic,
            tasks=tasks,
            student_solution=student_solution,
            first_result=json.dumps(data, ensure_ascii=False),
            synthetic_test=synthetic_test,
        )
        try:
            second_data = json.loads(second_raw)
        except (TypeError, json.JSONDecodeError):
            second_data = {}
        second_data = _apply_diagnostic_semantic_guards(
            data=second_data,
            tasks=tasks,
            student_solution=student_solution,
        )
        second_validated = validate_diagnostic_level_result(second_data, topic)
        return _reconcile_diagnostic_checks(
            first_validated,
            second_validated,
            topic,
        )
    return first_validated


def _needs_critical_recheck(result: dict) -> bool:
    return (
        result.get("status") != "correct"
        or bool(result.get("needs_teacher_review"))
        or float(result.get("confidence") or 0.0)
        < RECHECK_CONFIDENCE_THRESHOLD
    )


def _needs_diagnostic_recheck(result: dict) -> bool:
    # Диагностика влияет на Learning DNA, поэтому перепроверяется всегда.
    return bool(result.get("level_results"))


def _reconcile_homework_checks(first: dict, second: dict) -> dict:
    if first.get("status") == second.get("status"):
        result = dict(second)
        result["confidence"] = min(
            float(first.get("confidence") or 0.0),
            float(second.get("confidence") or 0.0),
        )
        result["recheck_status"] = "confirmed"
        result["first_check"] = first
        result["second_check"] = second
        return result

    return {
        **first,
        "status": "unclear",
        "confidence": min(
            float(first.get("confidence") or 0.0),
            float(second.get("confidence") or 0.0),
        ),
        "feedback": (
            "Две независимые AI-проверки дали разные заключения. "
            "Результат не засчитан автоматически."
        ),
        "hint": "Преподавателю нужно сравнить оба заключения.",
        "error_type": "ai_check_disagreement",
        "needs_teacher_review": True,
        "recheck_status": "disagreement",
        "first_check": first,
        "second_check": second,
    }


def _reconcile_diagnostic_checks(
    first: dict,
    second: dict,
    topic: str,
) -> dict:
    first_by_level = {
        item["level"]: item for item in first.get("level_results", [])
    }
    second_by_level = {
        item["level"]: item for item in second.get("level_results", [])
    }
    merged = []
    disagreement_levels = []
    for level in ("easy", "medium", "hard"):
        left = first_by_level[level]
        right = second_by_level[level]
        if left["status"] != right["status"]:
            disagreement_levels.append(level)
            merged.append({
                "level": level,
                "status": "unclear",
                "confidence": min(left["confidence"], right["confidence"]),
                "evidence": right.get("evidence") or left.get("evidence") or "",
                "feedback": (
                    "Первая и критическая проверки не согласились. "
                    f"Первая: {left['status']}; повторная: {right['status']}."
                ),
            })
        else:
            confirmed = dict(right)
            confirmed["confidence"] = min(
                left["confidence"],
                right["confidence"],
            )
            merged.append(confirmed)

    reconciled = validate_diagnostic_level_result(
        {
            "level_results": merged,
            "knowledge_boundary": (
                disagreement_levels[0]
                if disagreement_levels
                else second.get("knowledge_boundary")
            ),
            "recommended_action": (
                "Проверки согласны; вывод подтверждён повторно."
                if not disagreement_levels
                else "Есть расхождение двух AI-проверок. Нужна проверка преподавателя."
            ),
        },
        topic,
    )
    reconciled["recheck_status"] = (
        "confirmed" if not disagreement_levels else "disagreement"
    )
    reconciled["recheck_disagreement_levels"] = disagreement_levels
    reconciled["first_check"] = first
    reconciled["second_check"] = second
    if disagreement_levels:
        reconciled["needs_teacher_review"] = True
        reconciled["error_type"] = "ai_check_disagreement"
    return reconciled


def _apply_diagnostic_semantic_guards(
    *,
    data: dict,
    tasks: list[dict],
    student_solution: str,
) -> dict:
    """Correct known, mechanically verifiable diagnostic contradictions.

    The model remains responsible for general semantic assessment. Guards are
    deliberately narrow and run only when the task and its verified teacher
    answer explicitly define a minimum counterexample.
    """
    if not isinstance(data, dict):
        return {}

    level_results = data.get("level_results")
    if not isinstance(level_results, list):
        return data

    hard_task = tasks[2] if len(tasks) >= 3 else {}
    task_text = str(hard_task.get("task") or "")
    teacher_answer = str(hard_task.get("teacher_answer") or "")
    if "минимальн" not in task_text.casefold():
        return data

    expected_match = re.search(
        r"минимальн\w*\s+контрпример\D{0,20}n\s*=\s*(-?\d+)",
        teacher_answer,
        flags=re.IGNORECASE,
    )
    if not expected_match:
        return data

    hard_solution = _extract_numbered_solution_section(student_solution, 3)
    claimed_match = re.search(
        r"минимальн\w*\s+контрпример\D{0,20}n\s*=\s*(-?\d+)",
        hard_solution,
        flags=re.IGNORECASE,
    )
    if not claimed_match:
        return data

    expected = int(expected_match.group(1))
    claimed = int(claimed_match.group(1))
    if claimed == expected:
        return data

    for item in level_results:
        if isinstance(item, dict) and item.get("level") == "hard":
            item["status"] = "has_error"
            item["confidence"] = max(
                0.99,
                float(item.get("confidence") or 0.0),
            )
            item["evidence"] = claimed_match.group(0).strip()
            item["feedback"] = (
                f"Минимальный контрпример указан неверно: n = {claimed}. "
                f"Проверенный эталон задаёт n = {expected}."
            )
            data["knowledge_boundary"] = "hard"
            data["recommended_action"] = (
                "Лёгкий и средний уровни выполнены успешно. На сложном уровне "
                "нужно дополнительно потренировать поиск минимального "
                "граничного случая, начиная с наименьшего допустимого значения."
            )
            break
    return data


def _extract_numbered_solution_section(text: str, section_number: int) -> str:
    normalized = (text or "").replace("−", "-")
    pattern = re.compile(
        rf"(?ms)^\s*{section_number}\s*[.)]\s*(.*?)"
        rf"(?=^\s*{section_number + 1}\s*[.)]\s*|\Z)"
    )
    match = pattern.search(normalized)
    return match.group(1) if match else normalized
