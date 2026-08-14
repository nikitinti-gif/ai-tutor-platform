import json

import pytest

from src.ai_engine.diagnostics import open_diagnostic_case
from src.ai_engine.live_diagnostic_probes import build_live_probe
from src.skills.skill_graph import load_skill_map


def _case(task_number: int) -> dict:
    return open_diagnostic_case(
        task_number,
        "wrong",
        "expected",
        load_skill_map(),
    )


def test_task14_remainder_probe_requires_plain_numeric_remainder_question():
    case = _case(14)
    base = {"id": "task14_remainder_v2", "operation_index": 0}
    raw = json.dumps({
        "prompt_template": (
            "Число {n} делят на {base}. Чему равен остаток? "
            "Ответ дай обычным десятичным числом?"
        )
    }, ensure_ascii=False)
    probe = build_live_probe(case, base, raw, values=[911, 144], variant="default")
    assert probe["quality_gate"] == "passed"
    assert probe["expected_answers"] == ("11",)


def test_task14_rejects_probe_that_mixes_remainder_with_digit_symbol():
    case = _case(14)
    base = {"id": "task14_remainder_v2", "operation_index": 0}
    raw = json.dumps({
        "prompt_template": (
            "Число {n} делят на {base}. Какой символ или первая цифра справа "
            "получится из остатка? Ответ дай числом?"
        )
    }, ensure_ascii=False)
    with pytest.raises(ValueError, match="смешивает остаток"):
        build_live_probe(case, base, raw, values=[4140, 130], variant="default")


def test_task27_cluster_probe_is_distance_based_not_subjective():
    case = _case(27)
    base = {"id": "task27_clusters_v2", "operation_index": 0}
    raw = json.dumps({
        "prompt_template": (
            "Даны точки {points}. Внутри каждой пары расстояние {within_distance}, "
            "а между парами расстояние не меньше {between_min}. "
            "Сколько явно разделённых групп по расстояниям здесь получается?"
        )
    }, ensure_ascii=False)
    probe = build_live_probe(case, base, raw, values=[17, 7], variant="default")
    assert probe["quality_gate"] == "passed"
    assert probe["expected_answers"] == ("2",)


def test_task27_rejects_subjective_natural_cluster_wording():
    case = _case(27)
    base = {"id": "task27_clusters_v2", "operation_index": 0}
    raw = json.dumps({
        "prompt_template": (
            "Даны точки {points}; внутри пары расстояние {within_distance}, "
            "между парами не меньше {between_min}. Сколько естественных групп "
            "видно по расстояниям?"
        )
    }, ensure_ascii=False)
    with pytest.raises(ValueError, match="субъективное"):
        build_live_probe(case, base, raw, values=[17, 7], variant="default")


def test_pilot_operation_skill_ids_are_atomic_and_distinct():
    from src.ai_engine.diagnostics import PILOT_OPERATION_SKILLS
    from src.skills.skill_graph import get_skill

    assert len(PILOT_OPERATION_SKILLS) == 11
    assert len(set(PILOT_OPERATION_SKILLS.values())) == 11
    assert all(get_skill(skill_id) is not None for skill_id in PILOT_OPERATION_SKILLS.values())
    assert PILOT_OPERATION_SKILLS[(14, 0)] == "number_systems.calculate_remainder"
    assert PILOT_OPERATION_SKILLS[(27, 0)] == "programming.cluster_count_from_separation"
