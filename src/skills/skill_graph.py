"""Subject skill-map loading, validation and prerequisite traversal."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable


DEFAULT_MAP_PATH = Path(__file__).with_name("ege_informatics_2026.json")


class SkillMapValidationError(ValueError):
    """Raised when a subject map cannot safely drive a learning trajectory."""


@lru_cache(maxsize=4)
def load_skill_map(path: str | Path = DEFAULT_MAP_PATH) -> dict:
    map_path = Path(path)
    with map_path.open("r", encoding="utf-8") as source:
        skill_map = json.load(source)
    validate_skill_map(skill_map)
    return skill_map


def validate_skill_map(skill_map: dict) -> None:
    required = {"schema_version", "map_id", "domains", "skills", "tasks"}
    missing = required.difference(skill_map)
    if missing:
        raise SkillMapValidationError(f"Missing map fields: {sorted(missing)}")

    domain_ids = _unique_ids(skill_map["domains"], "domain")
    skills = skill_map["skills"]
    skill_ids = _unique_ids(skills, "skill")

    for skill in skills:
        if skill.get("domain") not in domain_ids:
            raise SkillMapValidationError(
                f"Unknown domain {skill.get('domain')!r} in skill {skill['id']!r}"
            )
        unknown = set(skill.get("prerequisites", [])).difference(skill_ids)
        if unknown:
            raise SkillMapValidationError(
                f"Unknown prerequisites for {skill['id']!r}: {sorted(unknown)}"
            )

    task_numbers = [task.get("number") for task in skill_map["tasks"]]
    expected = list(range(1, 28))
    if sorted(task_numbers) != expected:
        raise SkillMapValidationError(
            "EGE map must contain each task number 1..27 exactly once"
        )

    for task in skill_map["tasks"]:
        unknown = set(task.get("skills", [])).difference(skill_ids)
        if unknown:
            raise SkillMapValidationError(
                f"Unknown skills in task {task['number']}: {sorted(unknown)}"
            )
        if not task.get("operations") or not task.get("typical_errors"):
            raise SkillMapValidationError(
                f"Task {task['number']} lacks operations or typical errors"
            )
        mastery = task.get("mastery", {})
        if mastery.get("min_independent_attempts", 0) < 2:
            raise SkillMapValidationError(
                f"Task {task['number']} allows mastery from fewer than two attempts"
            )

    _assert_acyclic(skills)


def _unique_ids(items: Iterable[dict], kind: str) -> set[str]:
    ids = [item.get("id") for item in items]
    if any(not value for value in ids):
        raise SkillMapValidationError(f"Every {kind} must have a non-empty id")
    if len(ids) != len(set(ids)):
        raise SkillMapValidationError(f"Duplicate {kind} id")
    return set(ids)


def _assert_acyclic(skills: list[dict]) -> None:
    graph = {skill["id"]: skill.get("prerequisites", []) for skill in skills}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(skill_id: str) -> None:
        if skill_id in visiting:
            raise SkillMapValidationError(f"Prerequisite cycle at {skill_id!r}")
        if skill_id in visited:
            return
        visiting.add(skill_id)
        for prerequisite in graph[skill_id]:
            visit(prerequisite)
        visiting.remove(skill_id)
        visited.add(skill_id)

    for skill_id in graph:
        visit(skill_id)


def get_skill(skill_id: str, skill_map: dict | None = None) -> dict | None:
    subject_map = skill_map or load_skill_map()
    return next(
        (skill for skill in subject_map["skills"] if skill["id"] == skill_id),
        None,
    )


def get_skill_name(skill_id: str) -> str:
    skill = get_skill(skill_id)
    return skill["name"] if skill else skill_id


def migrate_legacy_focus(focus: str | None, skill_map: dict | None = None) -> str | None:
    if not focus:
        return None
    subject_map = skill_map or load_skill_map()
    if get_skill(focus, subject_map):
        return focus
    return subject_map.get("legacy_focus_migrations", {}).get(focus)


def prerequisites_met(
    skill: dict,
    skill_states: dict | None,
    mastered_skill_ids: set[str] | None = None,
) -> bool:
    states = skill_states or {}
    mastered = set(mastered_skill_ids or ())
    mastered.update(
        skill_id
        for skill_id, state in states.items()
        if isinstance(state, dict) and _is_mastered(state)
    )
    return set(skill.get("prerequisites", [])).issubset(mastered)


def select_next_skill(
    skill_states: dict | None = None,
    *,
    mastered_skill_ids: set[str] | None = None,
    skill_map: dict | None = None,
) -> str | None:
    """Choose the highest-priority weak skill whose prerequisites are mastered."""
    subject_map = skill_map or load_skill_map()
    states = skill_states or {}
    mastered = set(mastered_skill_ids or ())

    candidates = []
    for order, skill in enumerate(subject_map["skills"]):
        state = states.get(skill["id"], {})
        if skill["id"] in mastered or _is_mastered(state):
            continue
        if not prerequisites_met(skill, states, mastered):
            continue
        mastery = _mastery_percent(state)
        priority = int(skill.get("priority", 0))
        candidates.append((mastery, -priority, order, skill["id"]))

    return min(candidates)[3] if candidates else None


def _mastery_percent(state: dict) -> float:
    value = state.get("mastery_level", state.get("skill_level", 0))
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _is_mastered(state: dict) -> bool:
    if state.get("mastered") is True:
        return True
    evidence = int(state.get("evidence_count", state.get("attempts", 0)) or 0)
    exam_level = state.get("difficulty_max") in {"exam", "exam_level", 3}
    return _mastery_percent(state) >= 80 and evidence >= 2 and exam_level
