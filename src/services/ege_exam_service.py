"""Session helpers for the 27-task KЕГЭ open variant flow."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import json
import logging
import asyncio
from uuid import uuid4

from src.ai_engine.ege_open_variant_2026 import (
    EgeTask,
    OFFICIAL_FILES_URL,
    OPEN_VARIANT_2026,
)
from src.ai_engine.diagnostics import (
    CONTROL_PROBES,
    answer_control_probe,
    next_control_probe,
    open_diagnostic_case,
    apply_live_probe,
    diagnostic_probe_context,
)
from src.ai_engine.verification_engine import VerificationResult, verify_answer
from src.skills.skill_graph import load_skill_map

TOTAL_TASKS = 27
PROGRESS_WIDTH = 12
logger = logging.getLogger(__name__)


def _generate_self_check_probe(task_number: int, operation_index: int) -> dict:
    """Make one real Gemini probe with the same retries as the student flow."""
    from src.ai_engine.llm_client import LLMClient
    from src.ai_engine.live_diagnostic_probes import (
        _scenario,
        build_live_probe,
        generate_live_probe_values,
    )

    case = open_diagnostic_case(
        task_number,
        "synthetic_wrong_answer",
        "synthetic_expected_answer",
        load_skill_map(),
    )
    context = diagnostic_probe_context(case)
    base_probe = CONTROL_PROBES[task_number][operation_index]
    client = LLMClient()
    rejected_prompts: list[str] = []
    errors: list[str] = []

    for attempt_number in range(1, 4):
        raw = None
        try:
            values = generate_live_probe_values(task_number, operation_index)
            fields, _ = _scenario(task_number, operation_index, {"values": values})
            raw = client.generate_live_diagnostic_probe(
                task_number=task_number,
                operation_index=operation_index,
                skill_id=context["skill_id"],
                fields=fields,
                previous_prompts=rejected_prompts,
                synthetic_test=True,
            )
            generated = build_live_probe(
                case,
                {"id": base_probe["id"], "operation_index": operation_index},
                raw,
                previous_prompts=rejected_prompts,
                values=values,
            )
            generated["generation_attempts"] = attempt_number
            return generated
        except Exception as error:
            errors.append(
                f"attempt {attempt_number}: {type(error).__name__}: {error}"
            )
            try:
                rejected = str(json.loads(raw).get("prompt_template", "")).strip()
            except (TypeError, json.JSONDecodeError):
                rejected = ""
            if rejected:
                rejected_prompts.append(rejected)

    raise RuntimeError(" | ".join(errors))


async def run_live_diagnostic_self_check(bot) -> None:
    """Run all 11 pilot scenarios against real Gemini and notify the admin."""
    from config import ADMIN_TELEGRAM_ID

    scenarios = ((5, 4), (14, 3), (27, 4))
    passed: list[str] = []
    failed: list[str] = []
    logger.info("LIVE_DIAGNOSTIC_SELF_CHECK started scenarios=11")

    for task_number, operation_count in scenarios:
        for operation_index in range(operation_count):
            label = f"task={task_number} operation={operation_index}"
            try:
                result = await asyncio.to_thread(
                    _generate_self_check_probe,
                    task_number,
                    operation_index,
                )
                passed.append(label)
                logger.info(
                    "LIVE_DIAGNOSTIC_SELF_CHECK AI_PROBE %s attempts=%s prompt=%r",
                    label,
                    result["generation_attempts"],
                    result["prompt"],
                )
            except Exception as error:
                detail = f"{label}: {type(error).__name__}: {error}"
                failed.append(detail)
                logger.exception(
                    "LIVE_DIAGNOSTIC_SELF_CHECK FALLBACK_PROBE %s",
                    label,
                )

    status = "11/11 AI_PROBE" if not failed else f"{len(passed)}/11 AI_PROBE"
    logger.info(
        "LIVE_DIAGNOSTIC_SELF_CHECK completed status=%s failures=%s",
        status,
        " | ".join(failed) if failed else "none",
    )
    message = f"🧪 Реальная самопроверка Gemini завершена: {status}."
    if failed:
        message += "\n\nОшибки:\n" + "\n".join(f"• {item}" for item in failed)
    await bot.send_message(int(ADMIN_TELEGRAM_ID), message[:4000])


@dataclass(slots=True)
class ExamAttempt:
    attempt_id: str = field(default_factory=lambda: str(uuid4()))
    current_task: int = 1
    answers: dict[int, str] = field(default_factory=dict)
    results: dict[int, bool] = field(default_factory=dict)
    skipped: list[int] = field(default_factory=list)
    diagnostics: dict[int, dict] = field(default_factory=dict)

    @property
    def finished(self) -> bool:
        return self.current_task > TOTAL_TASKS

    @property
    def correct_count(self) -> int:
        return sum(self.results.values())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict | None) -> "ExamAttempt":
        data = data or {}
        return cls(
            str(data.get("attempt_id") or uuid4()),
            int(data.get("current_task", 1)),
            {int(k): str(v) for k, v in data.get("answers", {}).items()},
            {int(k): bool(v) for k, v in data.get("results", {}).items()},
            [int(x) for x in data.get("skipped", [])],
            {int(k): dict(v) for k, v in data.get("diagnostics", {}).items()},
        )


def get_task(number: int) -> EgeTask:
    return OPEN_VARIANT_2026[number]


def create_pilot_diagnostic_attempt() -> ExamAttempt:
    """Build an isolated attempt for reviewing pilot probes without an exam run."""
    skill_map = load_skill_map()
    attempt = ExamAttempt(current_task=TOTAL_TASKS + 1)
    for task_number in (5, 14, 27):
        attempt.answers[task_number] = "pilot_wrong_answer"
        attempt.results[task_number] = False
        attempt.diagnostics[task_number] = open_diagnostic_case(
            task_number=task_number,
            student_answer="pilot_wrong_answer",
            expected_answer="pilot_expected_answer",
            skill_map=skill_map,
        )
    return attempt


def _progress_bar(completed: int) -> str:
    completed = max(0, min(completed, TOTAL_TASKS))
    filled = round(PROGRESS_WIDTH * completed / TOTAL_TASKS)
    return "█" * filled + "░" * (PROGRESS_WIDTH - filled)


def _progress_text(attempt: ExamAttempt) -> str:
    completed = len(attempt.results)
    wrong_count = completed - attempt.correct_count - len(attempt.skipped)
    return (
        f"{_progress_bar(completed)} {completed}/{TOTAL_TASKS}\n"
        f"✅ {attempt.correct_count}   "
        f"❌ {max(0, wrong_count)}   "
        f"⏭ {len(attempt.skipped)}"
    )


def render_task(number: int) -> str:
    task = get_task(number)
    attachment_note = ""
    if task.attachment_required:
        attachment_note = (
            "\n\n📎 Для выполнения нужен файл варианта:\n"
            f"{OFFICIAL_FILES_URL}"
        )

    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🎓 КЕГЭ 2026\n"
        f"Задание {number} из {TOTAL_TASKS}\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📚 {task.title}\n\n"
        f"{task.statement}"
        f"{attachment_note}\n\n"
        f"✍️ {task.prompt}\n\n"
        "/skip_ege · /finish_ege · /cancel_ege"
    )


def submit_answer(attempt: ExamAttempt, answer: str) -> VerificationResult:
    if attempt.finished:
        raise ValueError("Экзамен уже завершён.")

    task_number = attempt.current_task
    result = verify_answer(task_number, answer)
    attempt.answers[task_number] = answer
    attempt.results[task_number] = result.is_correct
    if result.is_correct:
        attempt.diagnostics.pop(task_number, None)
    else:
        expected_answer = "\\n".join(
            " ".join(row) for row in result.expected_answer
        )
        attempt.diagnostics[task_number] = open_diagnostic_case(
            task_number=task_number,
            student_answer=answer,
            expected_answer=expected_answer,
            skill_map=load_skill_map(),
        )
    attempt.current_task += 1

    status = "✅ Верно!" if result.is_correct else "❌ Ответ неверный."
    feedback = f"{status}\n\n📊 {_progress_text(attempt)}"
    return replace(result, message=feedback)


def skip_task(attempt: ExamAttempt) -> int:
    if attempt.finished:
        raise ValueError("Экзамен уже завершён.")

    task_number = attempt.current_task
    if task_number not in attempt.skipped:
        attempt.skipped.append(task_number)
    attempt.results[task_number] = False
    attempt.current_task += 1
    return task_number


def render_summary(attempt: ExamAttempt) -> str:
    checked = sorted(attempt.results)
    wrong = [
        str(number)
        for number in checked
        if not attempt.results.get(number, False) and number not in attempt.skipped
    ]
    skipped = ", ".join(map(str, attempt.skipped)) if attempt.skipped else "нет"
    accuracy = round(attempt.correct_count * 100 / len(checked)) if checked else 0

    if attempt.correct_count >= 24:
        level = "🏆 Отличный результат"
    elif attempt.correct_count >= 18:
        level = "👍 Хорошая база"
    elif attempt.correct_count >= 10:
        level = "📚 Есть темы для повторения"
    else:
        level = "🧭 Нужен пошаговый план подготовки"

    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🏁 ВАРИАНТ ЗАВЕРШЁН\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{level}\n\n"
        f"✅ Верных: {attempt.correct_count}\n"
        f"📝 Проверено: {len(checked)} из {TOTAL_TASKS}\n"
        f"🎯 Точность: {accuracy}%\n\n"
        f"❌ Неверные: {', '.join(wrong) if wrong else 'нет'}\n"
        f"⏭ Пропущенные: {skipped}\n\n"
        "Проверка выполнена локально — без AI и Vision."
    )


def next_attempt_diagnostic_probe(attempt: ExamAttempt) -> dict | None:
    """Return the next probe across all incorrect tasks in exam order."""
    for task_number in sorted(attempt.diagnostics):
        case = attempt.diagnostics[task_number]
        if case.get("status") == "confirmed":
            continue
        probe = next_control_probe(case)
        if probe is not None:
            return {
                "task_number": task_number,
                **probe,
            }
    return None


def prepare_ai_diagnostic_probe(attempt: ExamAttempt) -> dict | None:
    """Generate fresh wording and inputs; Python validates and solves them."""
    probe = next_attempt_diagnostic_probe(attempt)
    if probe is None or probe.get("source") == "ai_wording_parameters_python_solver":
        return probe

    from src.ai_engine.llm_client import LLMClient
    from src.ai_engine.live_diagnostic_probes import build_live_probe, generate_live_probe_values, _scenario, PILOT_TASKS

    task_number = probe["task_number"]
    if task_number not in PILOT_TASKS:
        return probe
    case = attempt.diagnostics[task_number]
    context = diagnostic_probe_context(case)
    client = LLMClient()
    rejected_prompts: list[str] = []
    errors: list[str] = []
    for attempt_number in range(1, 4):
        raw = None
        try:
            values = generate_live_probe_values(task_number, probe["operation_index"])
            fields, _ = _scenario(task_number, probe["operation_index"], {"values": values})
            raw = client.generate_live_diagnostic_probe(
                task_number=task_number,
                operation_index=probe["operation_index"],
                skill_id=context["skill_id"],
                fields=fields,
                previous_prompts=context["previous_prompts"] + rejected_prompts,
                synthetic_test=True,
            )
            generated = build_live_probe(case, {
                "id": probe["base_probe_id"],
                "operation_index": probe["operation_index"],
            }, raw, previous_prompts=context["previous_prompts"] + rejected_prompts, values=values)
            break
        except Exception as error:
            errors.append(f"attempt {attempt_number}: {type(error).__name__}: {error}")
            try:
                rejected = str(json.loads(raw).get("prompt_template", "")).strip()
            except (TypeError, json.JSONDecodeError):
                rejected = ""
            if rejected:
                rejected_prompts.append(rejected)
    else:
        case["probe_generation"] = {"status": "fallback", "errors": errors}
        logger.warning(
            "FALLBACK_PROBE task=%s operation=%s errors=%s",
            task_number,
            probe["operation_index"],
            " | ".join(errors),
        )
        return next_attempt_diagnostic_probe(attempt)
    generated["generation_attempts"] = len(errors) + 1
    attempt.diagnostics[task_number] = apply_live_probe(case, generated)
    return next_attempt_diagnostic_probe(attempt)


def submit_diagnostic_answer(attempt: ExamAttempt, answer: str) -> dict:
    """Check one active local probe and persist its evidence in the attempt."""
    probe = next_attempt_diagnostic_probe(attempt)
    if probe is None:
        raise ValueError("Диагностические мини-пробы завершены.")

    task_number = probe["task_number"]
    case = answer_control_probe(
        attempt.diagnostics[task_number],
        probe["probe_id"],
        answer,
    )
    attempt.diagnostics[task_number] = case
    return {
        "task_number": task_number,
        "probe_id": probe["probe_id"],
        "is_correct": case["evidence"][-1]["is_correct"],
        "status": case["status"],
        "failed_step": case.get("failed_step"),
    }


def render_diagnostic_probe(attempt: ExamAttempt) -> str:
    probe = next_attempt_diagnostic_probe(attempt)
    if probe is None:
        return ""

    case = attempt.diagnostics[probe["task_number"]]
    generation = case.get("probe_generation", {})
    if probe.get("source") == "ai_wording_parameters_python_solver":
        source = "🧪 Источник: AI_PROBE\n"
    elif generation.get("status") == "fallback":
        errors = generation.get("errors") or []
        detail = f"Причина: {errors[-1]}\n" if errors else ""
        source = f"⚠️ Источник: FALLBACK_PROBE\n{detail}"
    else:
        source = ""
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔎 ДИАГНОСТИКА ОШИБКИ\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Задание КЕГЭ №{probe['task_number']}\n"
        "Проверяем один конкретный шаг решения.\n\n"
        f"{source}"
        f"{probe['prompt']}\n\n"
        "✍️ Отправь только ответ."
    )


def diagnostic_summary(attempt: ExamAttempt) -> str:
    confirmed = [
        case for case in attempt.diagnostics.values()
        if case.get("status") == "confirmed"
    ]
    unresolved = [
        case for case in attempt.diagnostics.values()
        if case.get("status") != "confirmed"
    ]
    lines = [
        "━━━━━━━━━━━━━━━━━━━━",
        "🧬 ДИАГНОСТИКА ЗАВЕРШЕНА",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"Подтверждённых точек ошибки: {len(confirmed)}",
        f"Не подтверждено мини-пробами: {len(unresolved)}",
    ]
    for case in confirmed:
        lines.append(
            f"• Задание №{case['task_number']}: {case['failed_step']}"
        )
    if unresolved:
        lines.append("")
        lines.append(
            "Неподтверждённые гипотезы не будут записаны в Learning DNA."
        )
    return "\n".join(lines)
