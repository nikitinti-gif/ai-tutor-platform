"""Subject skill-map loading, validation and prerequisite traversal."""

from __future__ import annotations

import json
import re
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

    # Atomic identity is global and must never be namespaced by an exam task.
    task_scoped = [skill_id for skill_id in skill_ids if re.match(r"^task_?\d+[.]", skill_id)]
    if task_scoped:
        raise SkillMapValidationError(
            f"Atomic skills must be global, not task-scoped: {sorted(task_scoped)}"
        )
    responsibilities: dict[tuple[str, str], str] = {}
    for skill in skills:
        semantic_key = re.sub(r"[^a-zа-я0-9]+", "", skill.get("name", "").casefold())
        key = (str(skill.get("domain")), semantic_key)
        if semantic_key and key in responsibilities:
            raise SkillMapValidationError(
                "Duplicate pedagogical responsibility: "
                f"{responsibilities[key]!r} and {skill['id']!r}"
            )
        responsibilities[key] = skill["id"]

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

    tasks_by_number = {task["number"]: task for task in skill_map["tasks"]}
    skills_by_id = {skill["id"]: skill for skill in skills}
    for skill in skills:
        for task_number in skill.get("exam_tasks", []):
            if task_number not in tasks_by_number:
                raise SkillMapValidationError(
                    f"Unknown exam task {task_number!r} in skill {skill['id']!r}"
                )
            if skill["id"] not in tasks_by_number[task_number].get("skills", []):
                raise SkillMapValidationError(
                    f"Skill {skill['id']!r} and task {task_number} are not bidirectional"
                )

    for task in skill_map["tasks"]:
        unknown = set(task.get("skills", [])).difference(skill_ids)
        if unknown:
            raise SkillMapValidationError(
                f"Unknown skills in task {task['number']}: {sorted(unknown)}"
            )
        missing_reverse = [
            skill_id
            for skill_id in task.get("skills", [])
            if task["number"] not in skills_by_id[skill_id].get("exam_tasks", [])
        ]
        if missing_reverse:
            raise SkillMapValidationError(
                f"Task {task['number']} has non-bidirectional skills: "
                f"{sorted(missing_reverse)}"
            )
        if not task.get("operations") or not task.get("typical_errors"):
            raise SkillMapValidationError(
                f"Task {task['number']} lacks operations or typical errors"
            )
        solution_mode = task.get("solution_mode")
        if solution_mode not in {"reasoning", "application", "programming"}:
            raise SkillMapValidationError(
                f"Task {task['number']} has invalid solution_mode: {solution_mode!r}"
            )
        if not str(task.get("solution_mode_label", "")).strip():
            raise SkillMapValidationError(
                f"Task {task['number']} lacks solution_mode_label"
            )
        mastery = task.get("mastery", {})
        if mastery.get("min_independent_attempts", 0) < 2:
            raise SkillMapValidationError(
                f"Task {task['number']} allows mastery from fewer than two attempts"
            )
        if not task.get("evidence"):
            raise SkillMapValidationError(f"Task {task['number']} lacks evidence model")

    attachments = skill_map.get("source", {}).get("attachments", {})
    for task in skill_map["tasks"]:
        requires_attachment = task["solution_mode"] == "application" or task["number"] in {17, 24, 26, 27}
        if requires_attachment and not attachments.get(str(task["number"])):
            raise SkillMapValidationError(
                f"Task {task['number']} requires a declared attachment"
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


def prerequisite_path(skill_id: str, skill_map: dict | None = None) -> list[str]:
    """Return prerequisites deepest-first, followed by the requested skill.

    A skill is emitted once even when several branches share the same
    prerequisite.  The order is deterministic and therefore safe to persist
    in an unfinished Telegram diagnostic session.
    """
    subject_map = skill_map or load_skill_map()
    if get_skill(skill_id, subject_map) is None:
        raise ValueError(f"Unknown skill: {skill_id}")

    ordered: list[str] = []
    visited: set[str] = set()

    def visit(current_id: str) -> None:
        if current_id in visited:
            return
        current = get_skill(current_id, subject_map)
        if current is None:  # guarded by validate_skill_map for descendants
            return
        for prerequisite_id in current.get("prerequisites", []):
            visit(prerequisite_id)
        visited.add(current_id)
        ordered.append(current_id)

    visit(skill_id)
    return ordered


def get_task(task_number: int, skill_map: dict | None = None) -> dict:
    """Return one validated EGE task definition."""
    subject_map = skill_map or load_skill_map()
    task = next(
        (item for item in subject_map["tasks"] if item["number"] == task_number),
        None,
    )
    if task is None:
        raise ValueError(f"Unknown EGE task: {task_number}")
    return task


def get_task_solution_mode(task_number: int, skill_map: dict | None = None) -> str:
    """Return reasoning/application/programming route for an EGE task."""
    return str(get_task(task_number, skill_map)["solution_mode"])


def tasks_by_solution_mode(mode: str, skill_map: dict | None = None) -> list[int]:
    """Return task numbers belonging to one tutor route."""
    if mode not in {"reasoning", "application", "programming"}:
        raise ValueError(f"Unknown solution mode: {mode}")
    subject_map = skill_map or load_skill_map()
    return [
        int(task["number"])
        for task in subject_map["tasks"]
        if task.get("solution_mode") == mode
    ]


def task_diagnostic_path(task_number: int, skill_map: dict | None = None) -> list[str]:
    """Build one recursive prerequisite path for an exam task."""
    subject_map = skill_map or load_skill_map()
    task = next(
        (item for item in subject_map["tasks"] if item["number"] == task_number),
        None,
    )
    if task is None:
        raise ValueError(f"Unknown EGE task: {task_number}")
    if not subject_map.get("skills"):
        return list(dict.fromkeys(task.get("skills", [])))

    ordered: list[str] = []
    for skill_id in task.get("skills", []):
        for path_skill_id in prerequisite_path(skill_id, subject_map):
            if path_skill_id not in ordered:
                ordered.append(path_skill_id)
    return ordered


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
