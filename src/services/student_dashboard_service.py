"""Read-only student knowledge dashboard built from Learning DNA and skill graph."""
from __future__ import annotations

from src.skills.skill_graph import load_skill_map
from src.services.learning_course import build_course, executable_skill_ids

STATUS_META = {
    "mastered": ("🟢", "Освоено"),
    "confirmed_weak": ("🔴", "Подтверждённый пробел"),
    "suspected": ("🟡", "Нужно уточнить"),
    "in_progress": ("🔵", "Сейчас изучаем"),
    "not_assessed": ("⚪", "Ещё не проверено"),
}
MODE_META = {
    "reasoning": ("📝", "Рассуждение"),
    "application": ("📊", "Работа с файлами/приложениями"),
    "programming": ("💻", "Программирование"),
}


def _status(skill_id: str, state: dict, plan_by_skill: dict) -> str:
    if state.get("mastered"):
        return "mastered"
    plan = plan_by_skill.get(skill_id, {})
    if plan.get("learning_status") in {"remediating", "retesting", "in_progress"}:
        return "in_progress"
    if plan.get("evidence_status") == "confirmed" or state.get("status") == "confirmed_weak":
        return "confirmed_weak"
    if state.get("status") in {"suspected", "needs_diagnosis"}:
        return "suspected"
    return "not_assessed"


def build_student_dashboard(dna: dict | None, exam_session: dict | None = None) -> dict:
    """Build a stable view-model; never create a second mastery model."""
    dna = dna or {}
    skill_map = load_skill_map()
    states = dna.get("skills") or {}
    plan = list((dna.get("trajectory") or {}).get("individual_plan") or [])
    course = build_course(plan, states)
    course_by_skill = {item.skill_id: item for item in course}
    plan_by_skill = {item.get("skill_id"): item for item in plan if item.get("skill_id")}
    task_modes = {task["number"]: task["solution_mode"] for task in skill_map["tasks"]}
    executable = executable_skill_ids()
    nodes = []
    for skill in skill_map["skills"]:
        skill_id = skill["id"]
        state = states.get(skill_id, {})
        exam_tasks = list(skill.get("exam_tasks", []))
        modes = sorted({task_modes[number] for number in exam_tasks})
        status = _status(skill_id, state, plan_by_skill)
        course_item = course_by_skill.get(skill_id)
        module_support = "READY_MODULE" if skill_id in executable else "PENDING_MODULE"
        if state.get("mastered"):
            course_status = "MASTERED"
            course_next_action = "Навык освоен"
        elif course_item:
            course_status = course_item.status
            course_next_action = course_item.next_action
        elif module_support == "PENDING_MODULE":
            course_status = "PENDING_MODULE"
            course_next_action = "Учебный модуль ещё не прошёл product gate"
        else:
            unmet = [p for p in skill.get("prerequisites", []) if not states.get(p, {}).get("mastered")]
            course_status = "BLOCKED_BY_PREREQUISITE" if unmet else "READY"
            course_next_action = None
        evidence = list(state.get("evidence_history") or state.get("remediation_evidence") or [])
        nodes.append({
            "skill_id": skill_id,
            "name": skill["name"],
            "status": status,
            "module_support": module_support,
            "course_status": course_status,
            "exam_tasks": exam_tasks,
            "prerequisites": list(skill.get("prerequisites", [])),
            "modes": modes,
            "evidence": evidence,
            "evidence_count": int(state.get("evidence_count", len(evidence))),
            "learning_support": "READY" if skill_id in executable else "PENDING",
            "current_course_stage": plan_by_skill.get(skill_id, {}).get("current_stage"),
            "next_step": course_next_action,
            "learning_path": plan_by_skill.get(skill_id, {}).get("learning_path", [
                "foundation", "basic", "intermediate", "transfer", "exam"
            ]),
            "mastery": int(state.get("mastery_level", 100 if state.get("mastered") else 0)),
            "next_action": plan_by_skill.get(skill_id, {}).get("action") or (
                "Начать learning module" if skill_id in executable else "Ожидать product-ready module"
            ),
        })
    counts = {status: sum(node["status"] == status for node in nodes) for status in STATUS_META}
    attempt = (exam_session or {}).get("attempt", exam_session or {})
    results = attempt.get("results", {}) if isinstance(attempt, dict) else {}
    score = sum(bool(value) for value in results.values())
    return {
        "student_id": dna.get("student_id"),
        "exam_score": score,
        "exam_total": 27,
        "counts": counts,
        "nodes": nodes,
        "edges": [
            {"from": prerequisite, "to": node["skill_id"]}
            for node in nodes for prerequisite in node["prerequisites"]
        ],
        "individual_plan": plan,
        "course": [
            {
                "skill_id": item.skill_id,
                "course_status": item.status,
                "module_support": (
                    "READY_MODULE" if item.skill_id in executable else "PENDING_MODULE"
                ),
                "next_action": item.next_action,
            }
            for item in course
        ],
        "next_focus_skill_id": (dna.get("trajectory") or {}).get("next_focus_skill_id"),
    }


def render_student_dashboard(view: dict) -> str:
    lines = [
        "━━━━━━━━━━━━━━━━━━━━", "🧬 МОЯ КАРТА ЗНАНИЙ", "━━━━━━━━━━━━━━━━━━━━", "",
        f"Пробный КЕГЭ: {view['exam_score']}/{view['exam_total']}",
    ]
    for status, (icon, label) in STATUS_META.items():
        lines.append(f"{icon} {label}: {view['counts'][status]}")
    for mode, (icon, label) in MODE_META.items():
        visible = [node for node in view["nodes"] if mode in node["modes"] and node["status"] != "not_assessed"]
        if not visible:
            continue
        lines.extend(["", f"{icon} {label}"])
        for node in visible:
            marker, status_label = STATUS_META[node["status"]]
            tasks = ", ".join(f"№{number}" for number in node["exam_tasks"])
            lines.append(f"{marker} {node['name']} — {status_label} (КЕГЭ {tasks})")
            lines.append(
                f"   Поддержка: {node['learning_support']}; evidence: {node['evidence_count']}; "
                f"prerequisites: {', '.join(node['prerequisites']) or 'нет'}; далее: {node['next_action']}"
            )
    lines.extend(["", "━━━━━━━━━━━━━━━━━━━━", "ТВОЙ УЧЕБНЫЙ МАРШРУТ", "━━━━━━━━━━━━━━━━━━━━"])
    if not view["individual_plan"]:
        lines.append("Подтверждённых пробелов пока нет. Продолжай практику.")
    nodes_by_skill = {node["skill_id"]: node for node in view["nodes"]}
    for index, item in enumerate(view["course"], 1):
        node = nodes_by_skill[item["skill_id"]]
        lines.append(f"{index}. {node['name']} — {item['course_status']}")
        lines.append(f"   Поддержка: {item['module_support']}")
        if item.get("next_action"):
            lines.append(f"   Следующий шаг: {item['next_action']}")
    lines.append("\nНажми «🎓 Начать обучение» или вернись позже — прогресс сохранён.")
    return "\n".join(lines)
