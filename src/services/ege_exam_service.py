"""Session helpers for the 27-task KЕГЭ open variant flow."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import json
import logging
import asyncio
import re
import time
from pathlib import Path
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
from src.ai_engine.diagnostic_evidence_gate import answer_bound_control_probe
from src.ai_engine.verification_engine import VerificationResult, verify_answer
from src.skills.skill_graph import load_skill_map

TOTAL_TASKS = 27
PROGRESS_WIDTH = 12
logger = logging.getLogger(__name__)


def _rate_limit_retry_delay(error: Exception) -> float | None:
    """Return Gemini's requested delay for a 429, otherwise ``None``."""
    text = str(error)
    if "429" not in text and "rate limit" not in text.lower() and "quota" not in text.lower():
        return None
    matches = re.findall(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", text, re.IGNORECASE)
    return min(max(float(matches[-1]) if matches else 60.0, 1.0) + 1.0, 65.0)


def _generate_wording_with_rate_limit_retry(client, **kwargs) -> str:
    """Retry the same Gemini request after the server-declared quota delay."""
    for rate_attempt in range(1, 4):
        try:
            return client.generate_live_diagnostic_probe(**kwargs)
        except Exception as error:
            delay = _rate_limit_retry_delay(error)
            if delay is None or rate_attempt == 3:
                raise
            logger.warning(
                "Gemini rate limit; retrying same diagnostic request in %.1fs (%s/2)",
                delay,
                rate_attempt,
            )
            time.sleep(delay)
    raise RuntimeError("Недостижимая ветка повтора Gemini.")
SELF_CHECK_RESULT_PATH = Path("/tmp/live_diagnostic_self_check.json")


def _generate_self_check_probe(task_number: int, operation_index: int) -> dict:
    """Make one real Gemini probe with the same retries as the student flow."""
    from src.ai_engine.llm_client import LLMClient
    from src.ai_engine.live_diagnostic_probes import (
        _scenario,
        build_live_probe,
        generate_live_probe_data,
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
            probe_data = generate_live_probe_data(task_number, operation_index)
            values = probe_data["values"]
            fields, _ = _scenario(task_number, operation_index, probe_data)
            raw = _generate_wording_with_rate_limit_retry(
                client,
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
                variant=str(probe_data["variant"]),
            )
            generated["generation_attempts"] = attempt_number
            generated["python_inputs"] = probe_data
            generated["scenario_fields"] = fields
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


async def run_live_diagnostic_self_check(_bot) -> None:
    """Run all 11 pilot scenarios and expose the result through logs/health."""
    scenarios = ((5, 4), (14, 3), (27, 4))
    passed: list[str] = []
    failed: list[str] = []
    probes: list[dict] = []
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
                probes.append({
                    "task_number": task_number,
                    "operation_index": operation_index,
                    "variant": result["variant"],
                    "prompt": result["prompt"],
                    "python_inputs": result["python_inputs"],
                    "scenario_fields": result["scenario_fields"],
                    "expected_answer": result["expected_answers"][0],
                    "generation_attempts": result["generation_attempts"],
                    "source": "AI_PROBE",
                })
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
    SELF_CHECK_RESULT_PATH.write_text(
        json.dumps(
            {
                "status": status,
                "passed": len(passed),
                "total": 11,
                "probes": probes,
                "failures": failed,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


@dataclass(slots=True)
class ExamAttempt:
    attempt_id: str = field(default_factory=lambda: str(uuid4()))
    current_task: int = 1
    answers: dict[int, str] = field(default_factory=dict)
    results: dict[int, bool] = field(default_factory=dict)
    skipped: list[int] = field(default_factory=list)
    diagnostics: dict[int, dict] = field(default_factory=dict)
    remediation: dict = field(default_factory=dict)

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
            dict(data.get("remediation", {})),
        )


TASK5_REMEDIATION = {
    "number_systems.decimal_binary_conversion": {
        "explanation": "Чтобы перевести десятичное число в двоичное, последовательно дели его на 2 и читай остатки снизу вверх.",
        "example": "Например, 13 = 1101₂: 13→6 остаток 1, 6→3 остаток 0, 3→1 остаток 1, затем старшая 1.",
        "hint": "Дели на 2, записывай остатки 0/1 и прочитай их в обратном порядке.",
        "control_prompt": "Контроль: переведи 10 из десятичной системы в двоичную.",
        "control_answers": ("1010",),
        "retest_prompt": "Перенос: переведи 25 из десятичной системы в двоичную.",
        "retest_answers": ("11001",),
        "verification_prompt": "Независимая проверка без подсказки: переведи 42 из десятичной системы в двоичную.",
        "verification_answers": ("101010",),
    },
    "algorithms.branch_from_last_bit": {
        "explanation": "Младший бит — последняя цифра двоичной записи. Именно по нему выбирается ветка алгоритма.",
        "example": "У 101101 последний бит 1, значит выбирается ветка для 1.",
        "hint": "Смотри только на крайнюю правую цифру двоичной записи.",
        "control_prompt": "Контроль: у записи 110010 какой младший бит?",
        "control_answers": ("0",),
        "retest_prompt": "Перенос: у записи 101011 какой младший бит?",
        "retest_answers": ("1",),
        "verification_prompt": "Независимая проверка: у записи 111100 какой младший бит?",
        "verification_answers": ("0",),
    },
    "algorithms.binary_suffix_append": {
        "explanation": "Приписать суффикс справа — значит оставить исходную двоичную запись без изменений и добавить указанные биты в конец.",
        "example": "К 101 приписать 11 → 10111.",
        "hint": "Не складывай числа: просто добавь указанные символы справа.",
        "control_prompt": "Контроль: к двоичной записи 1101 припиши справа 0.",
        "control_answers": ("11010",),
        "retest_prompt": "Перенос: к записи 1010 припиши справа 11.",
        "retest_answers": ("101011",),
        "verification_prompt": "Независимая проверка: к записи 11100 припиши справа 1.",
        "verification_answers": ("111001",),
    },
    "algorithms.integer_boundary_inequality": {
        "explanation": "Для строгого неравенства сначала найди границу, затем выбери наибольшее целое, которое всё ещё удовлетворяет знаку <.",
        "example": "3N+2<20 → N<6, значит наибольшее целое N равно 5.",
        "hint": "Реши неравенство и отдельно проверь ближайшее целое у границы.",
        "control_prompt": "Контроль: какое наибольшее целое N удовлетворяет 2N+1<12?",
        "control_answers": ("5",),
        "retest_prompt": "Перенос: какое наибольшее целое N удовлетворяет 4N+3<28?",
        "retest_answers": ("6",),
        "verification_prompt": "Независимая проверка: какое наибольшее целое N удовлетворяет 5N+2<38?",
        "verification_answers": ("7",),
    },
}


def _confirmed_task5_skill(attempt: ExamAttempt) -> str | None:
    case = attempt.diagnostics.get(5, {})
    if case.get("status") != "confirmed":
        return None
    for evidence in reversed(case.get("evidence", [])):
        skill_id = evidence.get("skill_id")
        if skill_id in TASK5_REMEDIATION and evidence.get("evidence_valid") is True and not evidence.get("is_correct"):
            return skill_id
    return None


def start_task5_remediation(attempt: ExamAttempt) -> dict | None:
    if attempt.remediation:
        return attempt.remediation
    skill_id = _confirmed_task5_skill(attempt)
    if not skill_id:
        return None
    attempt.remediation = {
        "task_number": 5, "skill_id": skill_id, "status": "remediating", "stage": "control",
        "control_attempts": 0, "retest_attempts": 0, "verification_attempts": 0,
        "learning_round": 1, "stage_history": [],
    }
    return attempt.remediation


def render_task5_remediation(attempt: ExamAttempt, *, include_lesson: bool | None = None) -> str:
    remediation = attempt.remediation
    lesson = TASK5_REMEDIATION[remediation["skill_id"]]
    stage = remediation["stage"]
    if stage == "control":
        if include_lesson is None:
            include_lesson = remediation["control_attempts"] == 0
        intro = ""
        if include_lesson:
            intro = "━━━━━━━━━━━━━━━━━━━━\n🧭 КОРОТКОЕ ОБУЧЕНИЕ · №5\n━━━━━━━━━━━━━━━━━━━━\n\nПравило: " + lesson["explanation"] + "\n\nРазобранный пример: " + lesson["example"] + "\n\n"
        elif remediation["control_attempts"]:
            intro = "💡 Подсказка: " + lesson["hint"] + "\n\nПравило ещё раз: " + lesson["explanation"] + "\n\n"
        return intro + lesson["control_prompt"] + "\n\nОтправь только ответ."
    if stage == "verification":
        return "━━━━━━━━━━━━━━━━━━━━\n🎯 НЕЗАВИСИМАЯ ПРОВЕРКА · №5\n━━━━━━━━━━━━━━━━━━━━\n\nЗдесь нет подсказки; данные отличаются от примеров.\n\n" + lesson["verification_prompt"] + "\n\nОтправь только ответ."
    intro = ""
    if remediation["retest_attempts"]:
        intro = "💡 Примени то же правило к новым данным.\n" + lesson["hint"] + "\n\n"
    return intro + lesson["retest_prompt"] + "\n\nОтправь только ответ."


def submit_task5_remediation_answer(attempt: ExamAttempt, answer: str) -> dict:
    remediation = attempt.remediation
    if not remediation or remediation.get("task_number") != 5 or remediation.get("status") not in {"remediating", "retesting"}:
        raise ValueError("Обучающий цикл №5 не запущен.")
    lesson = TASK5_REMEDIATION[remediation["skill_id"]]
    stage = remediation["stage"]
    normalized = answer.strip().lower().replace("ё", "е")
    expected = {item.lower().replace("ё", "е") for item in lesson[f"{stage}_answers"]}
    remediation[f"{stage}_attempts"] += 1
    is_correct = normalized in expected
    remediation.setdefault("stage_history", []).append({
        "stage": stage, "question": lesson[f"{stage}_prompt"],
        "canonical_answer": str(lesson[f"{stage}_answers"][0]), "student_answer": answer,
        "validator_result": is_correct, "is_correct": is_correct,
        "learning_round": remediation.get("learning_round", 1), "timestamp": time.time(),
    })
    if is_correct and stage == "control":
        remediation["stage"] = "retest"
    elif is_correct and stage == "retest":
        remediation["status"] = "retesting"; remediation["stage"] = "verification"
    elif is_correct:
        remediation["status"] = "mastered"; remediation["stage"] = "completed"
    elif stage == "verification":
        remediation["status"] = "remediating"; remediation["stage"] = "control"
        remediation["control_attempts"] = 0; remediation["retest_attempts"] = 0
        remediation["learning_round"] += 1
    return {"is_correct": is_correct, "status": remediation["status"], "stage": remediation["stage"]}


TASK14_REMEDIATION = {
    "BASE_REMAINDER_EXTRACTION": {
        "explanation": (
            "При переводе десятичного числа в другую систему каждый остаток "
            "становится очередной цифрой справа. На первом шаге достаточно "
            "вычислить n % base."
        ),
        "example": "Например: 83 = 13 × 6 + 5, поэтому первый остаток равен 5.",
        "hint": "Представь число как base × q + r, где 0 ≤ r < base.",
        "control_prompt": "Контроль: чему равен остаток при делении 74 на 6?",
        "control_answers": ("2",),
        "retest_prompt": (
            "Перенос: число 95 переводят в систему с основанием 7. "
            "Какой остаток получится на первом шаге?"
        ),
        "retest_answers": ("4",),
        "verification_prompt": (
            "Независимая проверка без подсказки: число 143 переводят в систему "
            "с основанием 9. Какой остаток получится на первом шаге?"
        ),
        "verification_answers": ("8",),
    },
    "BASE_DIGIT_VALUE_PROPERTY": {
        "explanation": (
            "В системах с основанием больше 10 буква — это цифра с числовым "
            "значением: A=10, B=11, C=12 и так далее. Свойство проверяют по значению."
        ),
        "example": "Например, C означает 12, поэтому C — цифра с чётным значением.",
        "hint": "Сначала замени букву числом: A=10, B=11, …, F=15.",
        "control_prompt": "Контроль: имеет ли цифра F чётное значение? Ответь да или нет.",
        "control_answers": ("нет", "no"),
        "retest_prompt": (
            "Возврат к заданию типа №14: учитывается ли цифра E при подсчёте "
            "цифр с чётным числовым значением? Ответь да или нет."
        ),
        "retest_answers": ("да", "yes"),
        "verification_prompt": (
            "Независимая проверка: учитывается ли цифра B при подсчёте цифр "
            "с чётным числовым значением? Ответь да или нет."
        ),
        "verification_answers": ("нет", "no"),
    },
    "BASE_MOST_SIGNIFICANT_DIGIT": {
        "explanation": (
            "При переводе делением остатки читают в обратном порядке, а последнее "
            "ненулевое частное ставят слева. Его нельзя потерять."
        ),
        "example": (
            "Например, остатки получались 5, 0, 2, а последнее частное равно 1. "
            "Читаем остатки наоборот и ставим 1 слева: получаем 1205."
        ),
        "hint": "Поставь последнее ненулевое частное слева, затем запиши остатки в обратном порядке.",
        "control_prompt": "Контроль: остатки получались 4, 3; последнее ненулевое частное равно 2. Запиши итоговую запись числа.",
        "control_answers": ("234",),
        "retest_prompt": "Перенос: остатки получались 5, 0, 2; последнее ненулевое частное равно 1. Запиши итоговую запись числа.",
        "retest_answers": ("1205",),
        "verification_prompt": "Независимая проверка: остатки получались 7, 1, 0, 3; последнее ненулевое частное равно 2. Запиши итоговую запись числа.",
        "verification_answers": ("23017",),
    },
}


def _confirmed_task14_gap(attempt: ExamAttempt) -> str | None:
    case = attempt.diagnostics.get(14, {})
    if case.get("status") != "confirmed":
        return None
    for evidence in reversed(case.get("evidence", [])):
        gap_id = evidence.get("gap_id")
        if gap_id in TASK14_REMEDIATION and not evidence.get("is_correct"):
            return gap_id
    return None


def start_task14_remediation(attempt: ExamAttempt) -> dict | None:
    """Start one deterministic teaching cycle for a confirmed task 14 gap."""
    if attempt.remediation:
        return attempt.remediation
    gap_id = _confirmed_task14_gap(attempt)
    if not gap_id:
        return None
    attempt.remediation = {
        "task_number": 14,
        "gap_id": gap_id,
        "status": "remediating",
        "stage": "control",
        "control_attempts": 0,
        "retest_attempts": 0,
        "verification_attempts": 0,
        "learning_round": 1,
        "stage_history": [],
    }
    return attempt.remediation


def render_task14_remediation(
    attempt: ExamAttempt,
    *,
    include_lesson: bool | None = None,
) -> str:
    remediation = attempt.remediation
    lesson = TASK14_REMEDIATION[remediation["gap_id"]]
    if remediation["stage"] == "control":
        if include_lesson is None:
            include_lesson = remediation["control_attempts"] == 0
        intro = ""
        if include_lesson:
            intro = (
                "━━━━━━━━━━━━━━━━━━━━\n"
                "🧭 КОРОТКОЕ ОБУЧЕНИЕ · №14\n"
                "━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Правило: {lesson['explanation']}\n\n"
                f"Разобранный пример: {lesson['example']}\n\n"
            )
        elif remediation["control_attempts"]:
            intro = (
                f"💡 Подсказка: {lesson['hint']}\n\n"
                f"Правило ещё раз: {lesson['explanation']}\n\n"
            )
        return intro + lesson["control_prompt"] + "\n\nОтправь только ответ."
    if remediation["stage"] == "verification":
        return (
            "━━━━━━━━━━━━━━━━━━━━\n"
            "🎯 НЕЗАВИСИМАЯ ПРОВЕРКА · №14\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Здесь нет подсказки и числа отличаются от примеров.\n\n"
            f"{lesson['verification_prompt']}\n\nОтправь только ответ."
        )
    intro = ""
    if remediation["retest_attempts"]:
        intro = (
            "💡 Почти получилось. Примени то же правило к новым данным.\n"
            f"{lesson['hint']}\n\n"
        )
    return intro + lesson["retest_prompt"] + "\n\nОтправь только ответ."


def submit_task14_remediation_answer(attempt: ExamAttempt, answer: str) -> dict:
    remediation = attempt.remediation
    if not remediation or remediation.get("status") not in {"remediating", "retesting"}:
        raise ValueError("Обучающий цикл №14 не запущен.")
    lesson = TASK14_REMEDIATION[remediation["gap_id"]]
    stage = remediation["stage"]
    normalized = answer.strip().lower().replace("ё", "е")
    expected = {item.lower().replace("ё", "е") for item in lesson[f"{stage}_answers"]}
    remediation[f"{stage}_attempts"] += 1
    is_correct = normalized in expected
    remediation.setdefault("stage_history", []).append({
        "stage": stage,
        "question": lesson[f"{stage}_prompt"],
        "canonical_answer": str(lesson[f"{stage}_answers"][0]),
        "student_answer": answer,
        "validator_result": is_correct,
        "is_correct": is_correct,
        "learning_round": remediation.get("learning_round", 1),
        "timestamp": time.time(),
    })
    if is_correct and stage == "control":
        remediation["stage"] = "retest"
    elif is_correct and stage == "retest":
        remediation["status"] = "retesting"
        remediation["stage"] = "verification"
    elif is_correct:
        remediation["status"] = "mastered"
        remediation["stage"] = "completed"
    elif stage == "verification":
        # A failed blind check is evidence that the skill is not stable yet.
        # Start a fresh teaching round instead of drilling the same question.
        remediation["status"] = "remediating"
        remediation["stage"] = "control"
        remediation["control_attempts"] = 0
        remediation["retest_attempts"] = 0
        remediation["learning_round"] += 1
    return {
        "is_correct": is_correct,
        "status": remediation["status"],
        "stage": remediation["stage"],
    }


TASK27_REMEDIATION = {
    "programming.cluster_count_from_separation": {
        "explanation": "Группы выделяют по сравнению расстояний: внутри группы точки близки, а между группами расстояние заметно больше.",
        "example": "Если внутри двух пар расстояние 2, а между парами минимум 14, это две явно разделённые группы.",
        "hint": "Сравни максимальное расстояние внутри группы с минимальным расстоянием между группами.",
        "control_prompt": "Контроль: внутри предполагаемых групп расстояния не больше 2, а между ними не меньше 12. Сколько явно разделённых групп: 1 или 2?",
        "control_answers": ("2",),
        "retest_prompt": "Перенос: есть три компактные пары точек. Внутри каждой пары расстояние 1, а между любыми парами не меньше 10. Сколько явно разделённых групп?",
        "retest_answers": ("3",),
        "verification_prompt": "Независимая проверка: точки образуют две компактные тройки; внутри тройки расстояния не больше 3, между тройками не меньше 18. Сколько групп подтверждается расстояниями?",
        "verification_answers": ("2",),
    },
    "programming.medoid_minimum": {
        "explanation": "Медоид выбирают по минимальной сумме расстояний до объектов своего кластера.",
        "example": "Если A=12, B=9, C=15, медоид B, потому что 9 — минимум.",
        "hint": "Выбери букву с наименьшей суммой.",
        "control_prompt": "Контроль: суммы A=14, B=11, C=17. Какой медоид выбрать?",
        "control_answers": ("B", "Б"),
        "retest_prompt": "Перенос: суммы A=21, B=16, C=19. Какой медоид оптимален?",
        "retest_answers": ("B", "Б"),
        "verification_prompt": "Независимая проверка: суммы A=18, B=23, C=15. Какой медоид оптимален?",
        "verification_answers": ("C", "С"),
    },
    "programming.cluster_label_count": {
        "explanation": "Размер кластера получают подсчётом объектов с нужной меткой.",
        "example": "В метках 1,2,1,3,1 метка 1 встречается три раза.",
        "hint": "Считай только метки, равные целевой.",
        "control_prompt": "Контроль: метки 1,2,2,3,2,1. Сколько объектов имеет метку 2?",
        "control_answers": ("3",),
        "retest_prompt": "Перенос: метки 3,1,3,2,3,3,1. Сколько объектов имеет метку 3?",
        "retest_answers": ("4",),
        "verification_prompt": "Независимая проверка: метки 2,2,1,3,1,1,2,1. Сколько объектов имеет метку 1?",
        "verification_answers": ("4",),
    },
    "programming.max_cluster_distance": {
        "explanation": "Максимальное расстояние — наибольшее из вычисленных значений.",
        "example": "Среди 4, 7, 3, 6 максимум равен 7.",
        "hint": "Сравни все значения и выбери наибольшее.",
        "control_prompt": "Контроль: расстояния 5, 12, 8, 9. Какое максимальное?",
        "control_answers": ("12",),
        "retest_prompt": "Перенос: расстояния 14, 6, 17, 11. Какое максимальное?",
        "retest_answers": ("17",),
        "verification_prompt": "Независимая проверка: расстояния 13, 19, 18, 7. Какое максимальное?",
        "verification_answers": ("19",),
    },
}


def _confirmed_task27_skill(attempt: ExamAttempt) -> str | None:
    case = attempt.diagnostics.get(27, {})
    if case.get("status") != "confirmed":
        return None
    for evidence in reversed(case.get("evidence", [])):
        skill_id = evidence.get("skill_id")
        if skill_id in TASK27_REMEDIATION and evidence.get("evidence_valid") is True and not evidence.get("is_correct"):
            return skill_id
    return None


def start_task27_remediation(attempt: ExamAttempt) -> dict | None:
    if attempt.remediation:
        return attempt.remediation
    skill_id = _confirmed_task27_skill(attempt)
    if not skill_id:
        return None
    attempt.remediation = {
        "task_number": 27, "skill_id": skill_id, "status": "remediating", "stage": "control",
        "control_attempts": 0, "retest_attempts": 0, "verification_attempts": 0,
        "learning_round": 1, "stage_history": [],
    }
    return attempt.remediation


def render_task27_remediation(attempt: ExamAttempt, *, include_lesson: bool | None = None) -> str:
    remediation = attempt.remediation
    lesson = TASK27_REMEDIATION[remediation["skill_id"]]
    stage = remediation["stage"]
    if stage == "control":
        if include_lesson is None:
            include_lesson = remediation["control_attempts"] == 0
        intro = ""
        if include_lesson:
            intro = "━━━━━━━━━━━━━━━━━━━━\n🧭 КОРОТКОЕ ОБУЧЕНИЕ · №27\n━━━━━━━━━━━━━━━━━━━━\n\nПравило: " + lesson["explanation"] + "\n\nРазобранный пример: " + lesson["example"] + "\n\n"
        elif remediation["control_attempts"]:
            intro = "💡 Подсказка: " + lesson["hint"] + "\n\nПравило ещё раз: " + lesson["explanation"] + "\n\n"
        return intro + lesson["control_prompt"] + "\n\nОтправь только ответ."
    if stage == "verification":
        return "━━━━━━━━━━━━━━━━━━━━\n🎯 НЕЗАВИСИМАЯ ПРОВЕРКА · №27\n━━━━━━━━━━━━━━━━━━━━\n\nЗдесь нет подсказки; данные отличаются от примеров.\n\n" + lesson["verification_prompt"] + "\n\nОтправь только ответ."
    intro = ""
    if remediation["retest_attempts"]:
        intro = "💡 Примени то же правило к новым данным.\n" + lesson["hint"] + "\n\n"
    return intro + lesson["retest_prompt"] + "\n\nОтправь только ответ."


def submit_task27_remediation_answer(attempt: ExamAttempt, answer: str) -> dict:
    remediation = attempt.remediation
    if not remediation or remediation.get("task_number") != 27 or remediation.get("status") not in {"remediating", "retesting"}:
        raise ValueError("Обучающий цикл №27 не запущен.")
    lesson = TASK27_REMEDIATION[remediation["skill_id"]]
    stage = remediation["stage"]
    normalized = answer.strip().lower().replace("ё", "е")
    expected = {item.lower().replace("ё", "е") for item in lesson[f"{stage}_answers"]}
    remediation[f"{stage}_attempts"] += 1
    is_correct = normalized in expected
    remediation.setdefault("stage_history", []).append({
        "stage": stage, "question": lesson[f"{stage}_prompt"],
        "canonical_answer": str(lesson[f"{stage}_answers"][0]),
        "student_answer": answer, "validator_result": is_correct, "is_correct": is_correct,
        "learning_round": remediation.get("learning_round", 1), "timestamp": time.time(),
    })
    if is_correct and stage == "control":
        remediation["stage"] = "retest"
    elif is_correct and stage == "retest":
        remediation["status"] = "retesting"; remediation["stage"] = "verification"
    elif is_correct:
        remediation["status"] = "mastered"; remediation["stage"] = "completed"
    elif stage == "verification":
        remediation["status"] = "remediating"; remediation["stage"] = "control"
        remediation["control_attempts"] = 0; remediation["retest_attempts"] = 0; remediation["verification_attempts"] = 0
        remediation["learning_round"] += 1
    return {"is_correct": is_correct, "status": remediation["status"], "stage": remediation["stage"]}


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


def bind_current_diagnostic_probe(attempt: ExamAttempt) -> dict | None:
    """Bind the exact probe that is about to be shown to the student's next answer."""
    probe = next_attempt_diagnostic_probe(attempt)
    if probe is None:
        return None
    task_number = probe["task_number"]
    case = attempt.diagnostics[task_number]
    pending = case.get("pending_probe") or {}
    if pending:
        if str(pending.get("probe_id", "")) != str(probe["probe_id"]):
            raise ValueError("Активная диагностическая проба не соответствует показываемому вопросу.")
        return probe
    attempt.diagnostics[task_number] = apply_live_probe(case, probe)
    return next_attempt_diagnostic_probe(attempt)


def mark_current_diagnostic_probe_displayed(attempt: ExamAttempt) -> dict:
    """Acknowledge only a probe that Telegram successfully delivered."""
    probe = next_attempt_diagnostic_probe(attempt)
    if probe is None:
        raise ValueError("Нет диагностической пробы для подтверждения показа.")
    task_number = probe["task_number"]
    case = attempt.diagnostics[task_number]
    pending = case.get("pending_probe") or {}
    if str(pending.get("probe_id", "")) != str(probe["probe_id"]):
        raise ValueError("Нельзя подтвердить показ непривязанной диагностической пробы.")
    pending = dict(pending)
    pending["displayed"] = True
    case = dict(case)
    case["pending_probe"] = pending
    attempt.diagnostics[task_number] = case
    return probe


def prepare_ai_diagnostic_probe(attempt: ExamAttempt) -> dict | None:
    """Generate fresh wording and inputs; Python validates and solves them."""
    probe = next_attempt_diagnostic_probe(attempt)
    if probe is None or probe.get("source") == "ai_wording_parameters_python_solver":
        return probe

    from src.ai_engine.llm_client import LLMClient
    from src.ai_engine.live_diagnostic_probes import build_live_probe, generate_live_probe_data, _scenario, PILOT_TASKS

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
            probe_data = generate_live_probe_data(task_number, probe["operation_index"])
            values = probe_data["values"]
            fields, _ = _scenario(task_number, probe["operation_index"], probe_data)
            raw = _generate_wording_with_rate_limit_retry(
                client,
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
            }, raw, previous_prompts=context["previous_prompts"] + rejected_prompts, values=values, variant=str(probe_data["variant"]))
            # Keep the Python-selected evidence role. The strict evidence gate
            # deliberately defaults a missing role to discrimination; losing
            # this field made every AI-worded retry look like a first probe.
            generated["probe_role"] = probe["probe_role"]
            generated["tested_step"] = probe["tested_step"]
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


def submit_diagnostic_answer(
    attempt: ExamAttempt,
    answer: str,
    *,
    student_id: int | str | None = None,
) -> dict:
    """Check one active local probe and persist its evidence in the attempt."""
    probe = next_attempt_diagnostic_probe(attempt)
    if probe is None:
        raise ValueError("Диагностические мини-пробы завершены.")

    task_number = probe["task_number"]
    current_case = attempt.diagnostics[task_number]
    if not current_case.get("pending_probe"):
        raise ValueError("Нет привязанной показанной диагностической пробы.")
    case = answer_bound_control_probe(
        current_case,
        probe["probe_id"],
        answer,
        student_id=student_id,
        attempt_id=attempt.attempt_id,
    )
    attempt.diagnostics[task_number] = case
    evidence = case["evidence"][-1]
    return {
        "task_number": task_number,
        "probe_id": probe["probe_id"],
        "is_correct": evidence["is_correct"],
        "status": case["status"],
        "failed_step": case.get("failed_step"),
        "gap_id": evidence.get("gap_id"),
        "probe_role": evidence.get("probe_role"),
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
    role_text = {
        "discrimination": "Различающая проба: отделяем пробел от случайной ошибки.",
        "transfer": "Проба на перенос: проверяем то же правило на новых данных.",
    }.get(probe.get("probe_role"), "Проверяем один конкретный шаг решения.")
    gap_text = ""
    if probe.get("description") and probe.get("required_rule"):
        gap_text = (
            f"\nГипотеза: {probe['description']}\n"
            f"Почему эта проба подходит: для ответа нужно применить правило — "
            f"{probe['required_rule']}\n"
        )
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "🔎 ДИАГНОСТИКА ОШИБКИ\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Задание КЕГЭ №{probe['task_number']}\n"
        f"{role_text}\n"
        f"{gap_text}\n"
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
        confirmed_gap = next(
            (item for item in case.get("gap_hypotheses", []) if item.get("status") == "confirmed"),
            None,
        )
        if confirmed_gap:
            lines.append(
                f"• Задание №{case['task_number']}: {confirmed_gap['description']}"
            )
            lines.append(
                f"  Что повторить: {confirmed_gap['required_rule']}"
            )
        else:
            lines.append(
                f"• Задание №{case['task_number']}: {case.get('failed_step') or 'точка ошибки подтверждена'}"
            )
    if unresolved:
        lines.append("")
        lines.append(
            "Неподтверждённые гипотезы не будут записаны в Learning DNA."
        )
    return "\n".join(lines)
