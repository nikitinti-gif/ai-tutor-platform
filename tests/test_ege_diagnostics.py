import json
from pathlib import Path

from src.services.ege_exam_service import (
    ExamAttempt,
    next_attempt_diagnostic_probe,
    submit_diagnostic_answer,
)
from src.ai_engine.diagnostics import (
    CONTROL_PROBES,
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


def test_wrong_final_answer_does_not_invent_failed_step():
    case = open_diagnostic_case(14, "1012", "1013", SKILL_MAP)
    assert case["status"] == DIAGNOSIS_NEEDS_EVIDENCE
    assert case["failed_step"] is None
    assert case["confidence"] == 0.0
    assert confirmed_cases([case]) == []


def test_self_report_is_only_probable():
    case = open_diagnostic_case(14, "1012", "1013", SKILL_MAP)
    case = record_student_step(case, 0)
    assert case["status"] == DIAGNOSIS_PROBABLE
    assert case["confidence"] < 0.5
    assert confirmed_cases([case]) == []


def test_failed_control_probe_confirms_exact_step():
    case = open_diagnostic_case(14, "1012", "1013", SKILL_MAP)
    case = record_control_probe(
        case,
        probe_id="base36_remainders_v1",
        tested_step="получать цифры делением с остатком",
        is_correct=False,
        observed_answer="остаток 38",
    )
    assert case["status"] == DIAGNOSIS_CONFIRMED
    assert case["failed_step"] == "получать цифры делением с остатком"
    assert case["confidence"] == 0.95
    assert confirmed_cases([case]) == [case]


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
    validate_control_probes(SKILL_MAP)
    case = open_diagnostic_case(14, "1012", "1013", SKILL_MAP)
    probe_ids = []
    for correct_answer in ("2", "2", "5"):
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


def test_every_probe_accepts_its_declared_answer_and_confirms_wrong_answer():
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
            assert failed["status"] == DIAGNOSIS_CONFIRMED
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

    passed = submit_diagnostic_answer(
        attempt,
        CONTROL_PROBES[1][0]["expected_answers"][0],
    )
    assert passed["is_correct"] is True
    assert next_attempt_diagnostic_probe(attempt)["probe_id"] == CONTROL_PROBES[1][1]["id"]

    failed = submit_diagnostic_answer(attempt, "заведомо неверный ответ")
    assert failed["is_correct"] is False
    assert failed["failed_step"] == attempt.diagnostics[1]["operations"][1]
    assert next_attempt_diagnostic_probe(attempt)["task_number"] == 2


def test_attempt_diagnostics_end_when_all_wrong_tasks_are_classified():
    skill_map = json.loads(
        (Path(__file__).parents[1] / "src" / "skills" / "ege_informatics_2026.json").read_text(encoding="utf-8")
    )
    attempt = ExamAttempt(current_task=28)
    attempt.diagnostics = {
        1: open_diagnostic_case(1, "wrong", "expected", skill_map),
    }

    submit_diagnostic_answer(attempt, "заведомо неверный ответ")
    assert attempt.diagnostics[1]["status"] == DIAGNOSIS_CONFIRMED
    assert next_attempt_diagnostic_probe(attempt) is None
