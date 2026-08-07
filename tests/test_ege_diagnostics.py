from src.ai_engine.diagnostics import (
    DIAGNOSIS_CONFIRMED,
    DIAGNOSIS_NEEDS_EVIDENCE,
    DIAGNOSIS_PROBABLE,
    confirmed_cases,
    open_diagnostic_case,
    record_control_probe,
    record_student_step,
)


SKILL_MAP = {
    "tasks": [
        {
            "number": 14,
            "title": "Системы счисления",
            "skills": ["number_systems.base_conversion"],
            "operations": ["получать цифры делением с остатком", "считать цифры"],
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
