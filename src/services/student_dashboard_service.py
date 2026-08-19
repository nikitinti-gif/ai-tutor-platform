"""Read-only student knowledge dashboard built from Learning DNA and skill graph."""
from __future__ import annotations

from src.skills.skill_graph import load_skill_map
from src.services.learning_course import build_course

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
    plan_by_skill = {item.get("skill_id"): item for item in plan if item.get("skill_id")}
    task_modes = {task["number"]: task["solution_mode"] for task in skill_map["tasks"]}
    nodes = []
    for skill in skill_map["skills"]:
        skill_id = skill["id"]
        state = states.get(skill_id, {})
        exam_tasks = list(skill.get("exam_tasks", []))
        modes = sorted({task_modes[number] for number in exam_tasks})
        status = _status(skill_id, state, plan_by_skill)
        evidence = list(state.get("evidence_history") or state.get("remediation_evidence") or [])
        nodes.append({
            "skill_id": skill_id,
            "name": skill["name"],
            "status": status,
            "exam_tasks": exam_tasks,
            "prerequisites": list(skill.get("prerequisites", [])),
            "modes": modes,
            "evidence": evidence,
            "next_step": plan_by_skill.get(skill_id, {}).get("action"),
            "learning_path": plan_by_skill.get(skill_id, {}).get("learning_path", [
                "foundation", "basic", "intermediate", "transfer", "exam"
            ]),
            "mastery": int(state.get("mastery_level", 100 if state.get("mastered") else 0)),
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
        "course": course,
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
    lines.extend(["", "━━━━━━━━━━━━━━━━━━━━", "ТВОЙ УЧЕБНЫЙ МАРШРУТ", "━━━━━━━━━━━━━━━━━━━━"])
    if not view["individual_plan"]:
        lines.append("Подтверждённых пробелов пока нет. Продолжай практику.")
    for index, item in enumerate(view["individual_plan"], 1):
        status = "подтверждено" if item.get("evidence_status") == "confirmed" else "нужно уточнить"
        lines.append(f"{index}. {item.get('skill_name', 'Навык')} — {status}")
        if item.get("action"):
            lines.append(f"   Следующий шаг: {item['action']}")
    inserted = [item for item in view["course"] if item.skill_id not in {
        row.get("skill_id") for row in view["individual_plan"]
    }]
    for item in inserted:
        lines.append(f"↳ Сначала освоить «{item.human_title}» — {item.status}")
    lines.append("\nНажми «🎓 Начать обучение» или вернись позже — прогресс сохранён.")
    return "\n".join(lines)
