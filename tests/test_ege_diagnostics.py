import asyncio
import json
from pathlib import Path
import random
import tempfile

import src.services.ege_exam_service as ege_exam_service

from src.services.ege_exam_service import (
    ExamAttempt,
    _generate_wording_with_rate_limit_retry,
    _rate_limit_retry_delay,
    bind_current_diagnostic_probe,
    mark_current_diagnostic_probe_displayed,
    next_attempt_diagnostic_probe,
    submit_diagnostic_answer,
)
from src.learning_dna.engine import apply_confirmed_ege_diagnostics
from src.ai_engine.diagnostic_evidence_gate import answer_bound_control_probe
from src.learning_dna.engine import (
    confirm_ege_remediation_mastery,
    set_ege_remediation_status,
)
from src.ai_engine.diagnostics import (
    CONTROL_PROBES,
    apply_ai_probe_wording,
    apply_live_probe,
    DIAGNOSIS_CONFIRMED,
    DIAGNOSIS_NEEDS_EVIDENCE,
    DIAGNOSIS_PROBABLE,
    confirmed_cases,
    confirmed_case_to_check_result,
    answer_control_probe,
    next_control_probe,
    open_diagnostic_case,
    record_control_probe,
    record_student_step,
    validate_control_probes,
)
from src.ai_engine.live_diagnostic_probes import build_live_probe, generate_live_probe_data, generate_live_probe_values, _scenario


SKILL_MAP = {
    "tasks": [
        {
            "number": 14,
            "title": "Системы счисления",
            "skills": ["number_systems.base_conversion"],
            "operations": [
                "получать цифры делением с остатком",
                "проверять свойство цифр",
                "считать без потери разрядов",
            ],
            "typical_errors": ["не обработан старший разряд"],
        }
    ]
}


def _answer_displayed_probe(case: dict, probe_id: str, answer: str) -> dict:
    """Test helper: explicitly model that the exact probe was displayed."""
    probe = next_control_probe(case)
    assert probe is not None
    assert probe["probe_id"] == probe_id
    case = apply_live_probe(case, probe)
    case["pending_probe"]["displayed"] = True
    return answer_bound_control_probe(case, probe_id, answer)


def test_wrong_final_answer_does_not_invent_failed_step():
    case = open_diagnostic_case(14, "1012", "1013", SKILL_MAP)
    assert case["status"] == DIAGNOSIS_NEEDS_EVIDENCE
    assert case["failed_step"] is None
    assert case["confidence"] == 0.0
    assert confirmed_cases([case]) == []


def test_ai_changes_wording_but_not_local_probe_identity():
    case = open_diagnostic_case(14, "wrong", "expected", SKILL_MAP)
    probe = next_control_probe(case)
    updated = apply_ai_probe_wording(
        case,
        probe,
        json.dumps({"prompt": "Вычислите остаток при первом делении."}),
    )
    displayed = next_control_probe(updated)
    assert displayed["probe_id"] == probe["probe_id"]
    assert displayed["prompt"] == "Вычислите остаток при первом делении."
    assert displayed["source"] == "ai_wording_local_answer"


def test_live_probe_uses_ai_wording_and_parameters_but_python_computes_answer():
    case = open_diagnostic_case(14, "wrong", "expected", SKILL_MAP)
    base = next_control_probe(case)
    generated = build_live_probe(
        case,
        {"id": base["base_probe_id"], "operation_index": base["operation_index"]},
        json.dumps({
            "prompt_template": (
                "Число {n} переводят в систему счисления с основанием {base}. "
                "Какой остаток даст первое деление?"
            ),
            "values": [137, 61],
        }),
    )
    assert "137" in generated["prompt"]
    assert generated["expected_answers"] == ("13",)
    assert generated["source"] == "ai_wording_parameters_python_solver"


def test_binary_conversion_uses_python_owned_direction_and_data():
    full_map = json.loads(
        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
    )
    case = open_diagnostic_case(5, "wrong", "expected", full_map)
    base = CONTROL_PROBES[5][0]
    generated = build_live_probe(
        case,
        {"id": base["id"], "operation_index": 0},
        json.dumps({
            "prompt_template": (
                "Число {source_number} дано в {source_system} системе. "
                "Запишите его в {target_system}. Какая запись получится?"
            ),
            "values": [102],
        }),
    )
    assert generated["expected_answers"] == ("1100110",)

    invalid = json.dumps({
        "prompt_template": (
            "Число {source_number} дано в {source_system} системе. "
            "Запишите его в {target_system}, используя 8 разрядов. Что получится?"
        ),
        "values": [102],
    })
    try:
        build_live_probe(case, {"id": base["id"], "operation_index": 0}, invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("Посторонние числа вне атомарного действия должны отклоняться")


def test_task5_branch_probe_accepts_only_verified_zero_and_one_constants():
    full_map = json.loads(
        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
    )
    case = open_diagnostic_case(5, "wrong", "expected", full_map)
    base = CONTROL_PROBES[5][1]
    valid = build_live_probe(
        case,
        {"id": base["id"], "operation_index": 1},
        json.dumps({
            "prompt_template": (
                "Для N={n} выберите ветку: 1, если последний двоичный бит равен 1, "
                "или 0, если он равен 0?"
            ),
            "values": [11],
        }),
    )
    assert valid["expected_answers"] == ("1", "ветка 1")

    invalid = json.dumps({
        "prompt_template": "Для N={n} выберите ветку 1, 0 или 2?",
        "values": [11],
    })
    try:
        build_live_probe(case, {"id": base["id"], "operation_index": 1}, invalid)
    except ValueError:
        pass
    else:
        raise AssertionError("Непроверяемая константа 2 должна отклоняться")


def test_gemini_429_retries_same_request_after_declared_delay(monkeypatch):
    class FakeClient:
        calls = 0

        def generate_live_diagnostic_probe(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("Error code: 429. Please retry in 1.363s")
            return '{"prompt_template": "ok"}'

    sleeps = []
    monkeypatch.setattr("src.services.ege_exam_service.time.sleep", sleeps.append)
    client = FakeClient()
    result = _generate_wording_with_rate_limit_retry(client, task_number=5)
    assert result == '{"prompt_template": "ok"}'
    assert client.calls == 2
    assert sleeps == [2.363]
    assert _rate_limit_retry_delay(RuntimeError("ordinary failure")) is None


def test_live_probe_rejects_invalid_parameter_shape():
    full_map = json.loads((Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8"))
    case = open_diagnostic_case(27, "wrong", "expected", full_map)
    base = next_control_probe(case)
    try:
        build_live_probe(case, {"id": base["base_probe_id"], "operation_index": 0}, json.dumps({
            "prompt_template": "Точки {points}. Сколько естественных кластеров образуют эти группы?",
            "values": [2],
        }))
    except ValueError:
        pass
    else:
        raise AssertionError("Некорректные параметры AI должны быть отклонены")


def test_live_probe_rejects_answer_leak():
    case = open_diagnostic_case(14, "wrong", "expected", SKILL_MAP)
    base = next_control_probe(case)
    raw = json.dumps({
        "prompt_template": (
            "Для числа {n} и основания {base} найдите остаток при делении. "
            "Ответ равен 13?"
        ),
        "values": [137, 61],
    })
    try:
        build_live_probe(case, {"id": base["base_probe_id"], "operation_index": 0}, raw)
    except ValueError:
        pass
    else:
        raise AssertionError("Вопрос с раскрытым ответом должен быть отклонён")


def test_live_probe_rejects_repeated_wording():
    case = open_diagnostic_case(14, "wrong", "expected", SKILL_MAP)
    base = next_control_probe(case)
    previous = "Число 137 переводят в систему с основанием 28. Какой остаток даст первое деление?"
    raw = json.dumps({
        "prompt_template": (
            "Число {n} переводят в систему с основанием {base}. "
            "Какой остаток даст первое деление?"
        ),
        "values": [211, 91],
    })
    try:
        build_live_probe(case, {"id": base["base_probe_id"], "operation_index": 0}, raw, [previous])
    except ValueError:
        pass
    else:
        raise AssertionError("Повтор прежней формулировки должен быть отклонён")


def test_live_probe_does_not_require_literal_skill_keywords():
    case = open_diagnostic_case(14, "wrong", "expected", SKILL_MAP)
    base = next_control_probe(case)
    raw = json.dumps({
        "prompt_template": "При первом шаге алгоритма для {n} и основания {base} какое значение нужно сохранить?",
        "values": [137, 61],
    })
    generated = build_live_probe(case, {"id": base["base_probe_id"], "operation_index": 0}, raw)
    assert generated["expected_answers"] == ("13",)


def test_all_pilot_scenarios_accept_valid_independent_wording():
    skill_map = json.loads(
        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
    )
    samples = {
        (5, 0): ("Запишите число {source_number} из {source_system} системы в {target_system}. Что получится?", [73]),
        (5, 1): ("Для числа {n} алгоритм смотрит на последний бит. Какую ветку он выберет: ветку один для единицы или ветку ноль для нуля?", [42]),
        (5, 2): ("К двоичной строке {binary} нужно присоединить справа суффикс {suffix}. Какая строка получится?", [19, 17]),
        (5, 3): ("Среди целых N от {start} до {limit} найдите наибольшее, для которого выполнено условие {expression} < {boundary}. Какое это N?", [20, 15]),
        (14, 0): ("Перевод числа {n} в основание {base} начинают с деления. Какой остаток возникнет на этом шаге?", [913, 67]),
        (14, 1): ("У цифры {digit} числовое значение {value}. Чётное ли оно? Ответьте да или нет.", [17]),
        (14, 2): ("Алгоритм получил {count} остатков, после чего осталось ненулевое частное. Сколько разрядов будет в записи?", [5]),
        (27, 0): ("На плоскости отмечены точки {points}. На сколько естественных групп-кластеров распадается набор?", [20, 8]),
        (27, 1): ("Для точек получены суммы расстояний: {sums}. Какая точка является медоидом?", [12, 5, 9]),
        (27, 2): ("После кластеризации получена последовательность меток {labels}. Сколько раз в ней встречается метка {target}?", [1, 2, 2, 3, 2, 1]),
        (27, 3): ("От медоида измерены расстояния до точек: {distances}. Каково максимальное расстояние?", [3, 11, 7, 5]),
    }
    for (task_number, operation_index), (template, values) in samples.items():
        case = open_diagnostic_case(task_number, "wrong", "expected", skill_map)
        base = CONTROL_PROBES[task_number][operation_index]
        generated = build_live_probe(
            case,
            {"id": base["id"], "operation_index": operation_index},
            json.dumps({"prompt_template": template, "values": values}),
        )
        assert generated["prompt"]
        assert generated["expected_answers"]


def test_pilot_gap_names_are_atomic_and_explain_what_to_practise():
    skill_map = json.loads(
        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
    )
    operations = {
        task["number"]: task["operations"][0]
        for task in skill_map["tasks"]
        if task["number"] in {5, 27}
    }

    assert operations[5] == "перевести число между десятичной и двоичной системами"
    assert operations[27] == "определить количество кластеров по пространственной близости"


def test_live_self_check_does_not_send_service_message_to_telegram():
    class BotThatMustStaySilent:
        async def send_message(self, *_args, **_kwargs):
            raise AssertionError("Служебная самопроверка не должна писать в Telegram")

    original_generator = ege_exam_service._generate_self_check_probe
    original_path = ege_exam_service.SELF_CHECK_RESULT_PATH
    try:
        ege_exam_service._generate_self_check_probe = lambda task, operation: {
            "variant": "test",
            "prompt": f"task={task}, operation={operation}",
            "python_inputs": {},
            "scenario_fields": {},
            "expected_answers": ("ok",),
            "generation_attempts": 1,
        }
        with tempfile.TemporaryDirectory() as directory:
            result_path = Path(directory) / "self-check.json"
            ege_exam_service.SELF_CHECK_RESULT_PATH = result_path
            asyncio.run(
                ege_exam_service.run_live_diagnostic_self_check(
                    BotThatMustStaySilent()
                )
            )
            result = json.loads(result_path.read_text(encoding="utf-8"))
    finally:
        ege_exam_service._generate_self_check_probe = original_generator
        ege_exam_service.SELF_CHECK_RESULT_PATH = original_path

    assert result["status"] == "11/11 AI_PROBE"


def test_suffix_probe_accepts_natural_gemini_wording_without_literal_right():
    full_map = json.loads(
        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
    )
    case = open_diagnostic_case(5, "wrong", "expected", full_map)
    base = CONTROL_PROBES[5][2]
    generated = build_live_probe(
        case,
        {"id": base["id"], "operation_index": 2},
        json.dumps({
            "prompt_template": (
                "Продолжите двоичную последовательность {binary}, "
                "добавив суффикс {suffix}. Какой результат получится?"
            ),
            "values": [19, 17],
        }),
    )
    assert generated["expected_answers"] == ("1001111",)


def test_task27_medoid_uses_one_atomic_placeholder_for_all_sums():
    full_map = json.loads(
        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
    )
    case = open_diagnostic_case(27, "wrong", "expected", full_map)
    base = CONTROL_PROBES[27][1]
    generated = build_live_probe(
        case,
        {"id": base["id"], "operation_index": 1},
        json.dumps({
            "prompt_template": (
                "Сравните суммы расстояний {sums}. Какой объект будет медоидом?"
            ),
            "values": [12, 5, 9],
        }),
    )
    assert "A — 12, B — 5, C — 9" in generated["prompt"]
    assert generated["expected_answers"] == ("B",)


def test_task27_label_count_accepts_natural_gemini_synonyms():
    full_map = json.loads(
        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
    )
    case = open_diagnostic_case(27, "wrong", "expected", full_map)
    base = CONTROL_PROBES[27][2]
    generated = build_live_probe(
        case,
        {"id": base["id"], "operation_index": 2},
        json.dumps({
            "prompt_template": (
                "Дана последовательность кластеров {labels}. "
                "Определите число элементов со значением {target}?"
            ),
            "values": [1, 2, 2, 3, 2, 1],
        }),
    )
    assert generated["expected_answers"] == ("1",)


def test_python_owns_fresh_inputs_for_all_pilot_scenarios():
    for task_number, operation_count in ((5, 4), (14, 3), (27, 4)):
        for operation_index in range(operation_count):
            values = generate_live_probe_values(task_number, operation_index)
            fields, answer = _scenario(task_number, operation_index, {"values": values})
            assert fields
            assert str(answer)


def test_task5_conversion_branch_supports_both_directions():
    full_map = json.loads(
        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
    )
    case = open_diagnostic_case(5, "wrong", "expected", full_map)
    base = CONTROL_PROBES[5][0]
    template = "Число {source_number} дано в {source_system} системе. Запишите его в {target_system}. Каков результат?"
    decimal_probe = build_live_probe(
        case, {"id": base["id"], "operation_index": 0},
        json.dumps({"prompt_template": template, "values": [42]}),
        variant="decimal_to_binary",
    )
    binary_probe = build_live_probe(
        case, {"id": base["id"], "operation_index": 0},
        json.dumps({"prompt_template": template, "values": [42]}),
        variant="binary_to_decimal",
    )
    assert decimal_probe["expected_answers"] == ("101010",)
    assert binary_probe["expected_answers"] == ("42",)
    assert "101010" in binary_probe["prompt"]
    assert decimal_probe["variant"] != binary_probe["variant"]


def test_task5_conversion_generator_selects_equivalent_variants():
    class LastChoiceRng(random.Random):
        def choice(self, seq):
            return seq[-1]

    data = generate_live_probe_data(5, 0, LastChoiceRng(7))
    assert data["variant"] == "binary_to_decimal"
    fields, answer = _scenario(5, 0, data)
    assert fields["source_system"] == "двоичной"
    assert str(answer).isdigit()


def test_self_report_is_only_probable():
    case = open_diagnostic_case(14, "1012", "1013", SKILL_MAP)
    case = record_student_step(case, 0)
    assert case["status"] == DIAGNOSIS_PROBABLE
    assert case["confidence"] < 0.5
    assert confirmed_cases([case]) == []


def test_one_failed_control_probe_is_only_probable():
    case = open_diagnostic_case(14, "1012", "1013", SKILL_MAP)
    case = record_control_probe(
        case,
        probe_id="base36_remainders_v1",
        tested_step="получать цифры делением с остатком",
        is_correct=False,
        observed_answer="остаток 38",
    )
    assert case["status"] == DIAGNOSIS_PROBABLE
    assert case["failed_step"] == "получать цифры делением с остатком"
    assert case["confidence"] == 0.6
    assert confirmed_cases([case]) == []


def test_task14_opens_named_gap_hypotheses():
    case = open_diagnostic_case(14, "1012", "1013", SKILL_MAP)

    assert [item["gap_id"] for item in case["gap_hypotheses"]] == [
        "BASE_REMAINDER_EXTRACTION",
        "BASE_DIGIT_VALUE_PROPERTY",
        "BASE_MOST_SIGNIFICANT_DIGIT",
    ]
    assert all(item["status"] == "suspected" for item in case["gap_hypotheses"])


def test_task14_requires_discrimination_and_transfer_to_confirm_gap():
    case = open_diagnostic_case(14, "wrong", "expected", SKILL_MAP)
    first = next_control_probe(case)
    assert first["probe_role"] == "discrimination"
    assert first["gap_id"] == "BASE_REMAINDER_EXTRACTION"

    case = answer_control_probe(case, first["probe_id"], "wrong")
    assert case["status"] == DIAGNOSIS_PROBABLE
    assert case["gap_hypotheses"][0]["status"] == "probing"

    transfer = next_control_probe(case)
    assert transfer["probe_role"] == "transfer"
    case = answer_control_probe(case, transfer["probe_id"], "wrong")

    assert case["status"] == DIAGNOSIS_CONFIRMED
    assert case["gap_hypotheses"][0]["status"] == "confirmed"
    signal = confirmed_case_to_check_result(case)
    assert signal["confirmed_gap"]["gap_id"] == "BASE_REMAINDER_EXTRACTION"


def test_passed_transfer_rejects_task14_gap_hypothesis():
    case = open_diagnostic_case(14, "wrong", "expected", SKILL_MAP)
    first = next_control_probe(case)
    case = answer_control_probe(case, first["probe_id"], "wrong")
    transfer = next_control_probe(case)
    case = answer_control_probe(case, transfer["probe_id"], "2")

    assert case["status"] == DIAGNOSIS_NEEDS_EVIDENCE
    assert case["gap_hypotheses"][0]["status"] == "not_confirmed"
    assert confirmed_cases([case]) == []


def test_failure_in_another_step_does_not_confirm_current_skill():
    case = open_diagnostic_case(14, "wrong", "expected", SKILL_MAP)
    case = record_control_probe(case, probe_id="first", tested_step=case["operations"][0], is_correct=False, observed_answer="x")
    case = record_control_probe(case, probe_id="recovery", tested_step=case["operations"][0], is_correct=True, observed_answer="2")
    case = record_control_probe(case, probe_id="second", tested_step=case["operations"][1], is_correct=False, observed_answer="x")
    assert case["status"] == DIAGNOSIS_PROBABLE
    assert confirmed_cases([case]) == []


def test_medoid_probe_accepts_cyrillic_lookalike_for_latin_b():
    skill_map = {
        "tasks": [{
            "number": 27,
            "title": "Кластеризация",
            "skills": ["clustering.medoid"],
            "operations": [
                "разделить точки на кластеры",
                "найти медоид",
                "отфильтровать точки по метке",
                "найти максимальное расстояние",
            ],
            "typical_errors": [],
        }]
    }
    case = open_diagnostic_case(27, "wrong", "correct", skill_map)
    case = answer_control_probe(case, "task27_clusters_v2", "2")
    updated = answer_control_probe(case, "task27_medoid_v2", "В")

    assert updated["evidence"][-1]["is_correct"] is True
    assert updated["status"] != DIAGNOSIS_CONFIRMED


def test_passed_probe_rejects_previous_hypothesis():
    case = record_student_step(
        open_diagnostic_case(14, "1012", "1013", SKILL_MAP), 0
    )
    case = record_control_probe(
        case,
        probe_id="base36_remainders_v1",
        tested_step="получать цифры делением с остатком",
        is_correct=True,
        observed_answer="верно",
    )
    assert case["status"] == DIAGNOSIS_NEEDS_EVIDENCE
    assert case["failed_step"] is None
    assert confirmed_cases([case]) == []


def test_task14_probes_cover_every_operation():
    full_map = json.loads(
        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
    )
    validate_control_probes(full_map)
    case = open_diagnostic_case(14, "1012", "1013", SKILL_MAP)
    probe_ids = []
    for correct_answer in ("2", "да", "4"):
        probe = next_control_probe(case)
        probe_ids.append(probe["probe_id"])
        case = answer_control_probe(case, probe["probe_id"], correct_answer)
    assert len(set(probe_ids)) == len(SKILL_MAP["tasks"][0]["operations"])
    assert next_control_probe(case) is None
    assert confirmed_cases([case]) == []


def test_failed_task14_probe_creates_learning_dna_signal():
    case = open_diagnostic_case(14, "1012", "1013", SKILL_MAP)
    probe = next_control_probe(case)
    case = answer_control_probe(case, probe["probe_id"], "38")
    probe = next_control_probe(case)
    case = answer_control_probe(case, probe["probe_id"], "38")
    signal = confirmed_case_to_check_result(case)
    assert signal["status"] == "has_error"
    assert signal["skill_id"] == "number_systems.base_conversion"
    assert signal["source"] == "local_control_probe"
    assert signal["confidence"] == 0.95


def test_unconfirmed_case_cannot_become_learning_dna_signal():
    case = open_diagnostic_case(14, "1012", "1013", SKILL_MAP)
    try:
        confirmed_case_to_check_result(case)
    except ValueError as error:
        assert "подтверждённую" in str(error)
    else:
        raise AssertionError("Unconfirmed diagnosis leaked into Learning DNA")


def test_all_27_tasks_have_one_probe_per_operation():
    skill_map_path = Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json"
    if not skill_map_path.exists():
        skill_map_path = Path(__file__).parents[1] / "repo_snapshot" / "src" / "skills" / "ege_informatics_2026.json"
    skill_map = json.loads(skill_map_path.read_text(encoding="utf-8"))
    validate_control_probes(skill_map)

    assert set(CONTROL_PROBES) == set(range(1, 28))
    for task in skill_map["tasks"]:
        probes = CONTROL_PROBES[task["number"]]
        assert len(probes) == len(task["operations"])
        assert {probe["operation_index"] for probe in probes} == set(
            range(len(task["operations"]))
        )


def test_every_probe_accepts_its_declared_answer_and_keeps_one_error_probable():
    skill_map_path = Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json"
    if not skill_map_path.exists():
        skill_map_path = Path(__file__).parents[1] / "repo_snapshot" / "src" / "skills" / "ege_informatics_2026.json"
    skill_map = json.loads(skill_map_path.read_text(encoding="utf-8"))

    for task_number, probes in CONTROL_PROBES.items():
        for probe in probes:
            case = open_diagnostic_case(task_number, "wrong", "expected", skill_map)
            passed = answer_control_probe(case, probe["id"], probe["expected_answers"][0])
            assert passed["status"] == DIAGNOSIS_NEEDS_EVIDENCE
            assert passed["failed_step"] is None

            failed = answer_control_probe(case, probe["id"], "заведомо неверный ответ")
            assert failed["status"] == DIAGNOSIS_PROBABLE
            assert failed["failed_step"] == case["operations"][probe["operation_index"]]



def test_attempt_diagnostics_advance_across_steps_and_tasks():
    attempt = ExamAttempt(current_task=28)
    attempt.diagnostics = {
        1: open_diagnostic_case(1, "wrong", "expected", json.loads(
            (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
        )),
        2: open_diagnostic_case(2, "wrong", "expected", json.loads(
            (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
        )),
    }

    first = next_attempt_diagnostic_probe(attempt)
    assert first["task_number"] == 1
    assert first["probe_id"] == CONTROL_PROBES[1][0]["id"]

    bind_current_diagnostic_probe(attempt)
    mark_current_diagnostic_probe_displayed(attempt)
    passed = submit_diagnostic_answer(
        attempt,
        CONTROL_PROBES[1][0]["expected_answers"][0],
    )
    assert passed["is_correct"] is True
    assert next_attempt_diagnostic_probe(attempt)["probe_id"] == CONTROL_PROBES[1][1]["id"]

    bind_current_diagnostic_probe(attempt)
    mark_current_diagnostic_probe_displayed(attempt)
    failed = submit_diagnostic_answer(attempt, "заведомо неверный ответ")
    assert failed["is_correct"] is False
    assert failed["failed_step"] == attempt.diagnostics[1]["operations"][1]
    retry = next_attempt_diagnostic_probe(attempt)
    assert retry["task_number"] == 1
    assert retry["base_probe_id"] == CONTROL_PROBES[1][1]["id"]
    bind_current_diagnostic_probe(attempt)
    mark_current_diagnostic_probe_displayed(attempt)
    submit_diagnostic_answer(attempt, "заведомо неверный ответ")
    assert next_attempt_diagnostic_probe(attempt)["task_number"] == 2


def test_attempt_diagnostics_end_when_all_wrong_tasks_are_classified():
    skill_map = json.loads(
        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
    )
    attempt = ExamAttempt(current_task=28)
    attempt.diagnostics = {
        1: open_diagnostic_case(1, "wrong", "expected", skill_map),
    }

    bind_current_diagnostic_probe(attempt)
    mark_current_diagnostic_probe_displayed(attempt)
    submit_diagnostic_answer(attempt, "заведомо неверный ответ")
    bind_current_diagnostic_probe(attempt)
    mark_current_diagnostic_probe_displayed(attempt)
    submit_diagnostic_answer(attempt, "заведомо неверный ответ")
    assert attempt.diagnostics[1]["status"] == DIAGNOSIS_CONFIRMED
    assert next_attempt_diagnostic_probe(attempt) is None



def test_confirmed_ege_evidence_is_applied_to_learning_dna_exactly_once():
    skill_map = json.loads(
        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
    )
    attempt = ExamAttempt(attempt_id="attempt-fixed", current_task=28)
    case = open_diagnostic_case(14, "wrong", "expected", skill_map)
    probe = next_control_probe(case)
    case = _answer_displayed_probe(case, probe["probe_id"], "заведомо неверно")
    second_probe = next_control_probe(case)
    attempt.diagnostics = {
        14: _answer_displayed_probe(
            case, second_probe["probe_id"], "заведомо неверно"
        )
    }

    dna, first = apply_confirmed_ege_diagnostics(None, 123, attempt)
    signal_count = len(dna["signals"])
    skill_attempts = dna["skills"]["number_systems.base_conversion"]["attempts"]

    dna, second = apply_confirmed_ege_diagnostics(dna, 123, attempt)

    assert first["applied_count"] == 1
    assert second["applied_count"] == 0
    assert len(dna["processed_evidence_ids"]) == 1
    assert len(dna["signals"]) == signal_count
    assert dna["skills"]["number_systems.base_conversion"]["attempts"] == skill_attempts
    assert len(dna["trajectory"]["individual_plan"]) == 1
    assert dna["trajectory"]["next_focus"] == attempt.diagnostics[14]["failed_step"]


def test_unconfirmed_ege_case_does_not_change_learning_dna_or_plan():
    skill_map = json.loads(
        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
    )
    attempt = ExamAttempt(attempt_id="attempt-unconfirmed", current_task=28)
    attempt.diagnostics = {
        14: open_diagnostic_case(14, "wrong", "expected", skill_map)
    }

    dna, result = apply_confirmed_ege_diagnostics(None, 123, attempt)

    assert result["applied_count"] == 0
    assert dna["signals"] == []
    assert dna["processed_evidence_ids"] == []
    assert dna["trajectory"]["individual_plan"] == []
    assert dna["trajectory"]["next_focus"] is None


def test_remediation_status_updates_existing_task14_plan():
    attempt = ExamAttempt(attempt_id="attempt-remediation", current_task=28)
    case = open_diagnostic_case(14, "wrong", "expected", json.loads(
        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
    ))
    case = _answer_displayed_probe(case, next_control_probe(case)["probe_id"], "wrong")
    case = _answer_displayed_probe(case, next_control_probe(case)["probe_id"], "wrong")
    attempt.diagnostics[14] = case
    dna, _ = apply_confirmed_ege_diagnostics(None, 123, attempt)

    updated = set_ege_remediation_status(dna, 14, "retesting")

    assert updated["trajectory"]["individual_plan"][0]["learning_status"] == "retesting"
    assert updated["trajectory"]["remediation_status"] == "retesting"


def test_verified_task14_remediation_marks_skill_mastered_once():
    attempt = ExamAttempt(attempt_id="attempt-verified", current_task=28)
    case = open_diagnostic_case(14, "wrong", "expected", json.loads(
        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
    ))
    case = _answer_displayed_probe(case, next_control_probe(case)["probe_id"], "wrong")
    case = _answer_displayed_probe(case, next_control_probe(case)["probe_id"], "wrong")
    attempt.diagnostics[14] = case
    dna, _ = apply_confirmed_ege_diagnostics(None, 123, attempt)

    updated = confirm_ege_remediation_mastery(dna, 14, attempt.attempt_id)
    evidence_count = updated["skills"]["number_systems.base_conversion"]["evidence_count"]
    updated = confirm_ege_remediation_mastery(updated, 14, attempt.attempt_id)

    skill = updated["skills"]["number_systems.base_conversion"]
    assert skill["mastered"] is True
    assert skill["mastery_level"] == 100
    assert skill["evidence_count"] == evidence_count
    assert updated["trajectory"]["individual_plan"][0]["learning_status"] == "mastered"
