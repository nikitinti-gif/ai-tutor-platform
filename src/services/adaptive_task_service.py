from datetime import datetime


SYSTEMS_OF_NUMERATION_TASKS = [
    {
        "level": "Лёгкий",
        "task": "Переведи двоичное число 10101₂ в десятичную систему.",
        "teacher_answer": "21₁₀ (16 + 4 + 1).",
        "purpose": "Проверить веса разрядов и базовое сложение.",
    },
    {
        "level": "Средний",
        "task": (
            "Найди и исправь ошибку: 11010₂ = 16 + 4 + 2 = 22₁₀. "
            "Распиши ненулевые разряды."
        ),
        "teacher_answer": (
            "11010₂ = 16 + 8 + 2 = 26₁₀; во втором разряде слева "
            "стоит единица с весом 8."
        ),
        "purpose": "Отделить реальную ошибку от корректного разложения.",
    },
    {
        "level": "Сложный",
        "task": (
            "Переведи 101101₂ в десятичную систему, затем измени в двоичной "
            "записи ровно один разряд так, чтобы число уменьшилось на 8."
        ),
        "teacher_answer": (
            "101101₂ = 45₁₀; заменить разряд 2³: "
            "101101₂ → 100101₂ = 37₁₀."
        ),
        "purpose": "Проверить перенос понимания позиционного веса разряда.",
    },
]


def build_adaptive_task_draft(dna: dict) -> dict:
    topic = (dna.get("trajectory") or {}).get("next_focus")
    if topic == "Системы счисления":
        tasks = SYSTEMS_OF_NUMERATION_TASKS
    else:
        raise ValueError("Для этой темы пока нет проверенного шаблона заданий.")

    return {
        "student_id": dna.get("student_id"),
        "topic": topic,
        "tasks": [dict(task) for task in tasks],
        "status": "teacher_draft",
        "created_by": "verified_adaptive_template_v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def format_adaptive_task_draft_for_teacher(draft: dict) -> str:
    sections = []
    for index, task in enumerate(draft["tasks"], start=1):
        sections.append(
            f"{index}. {task['level']} уровень\n"
            f"Задание: {task['task']}\n"
            f"Ответ для преподавателя: {task['teacher_answer']}\n"
            f"Цель: {task['purpose']}"
        )

    return (
        "📝 Адаптивный черновик для преподавателя\n\n"
        f"Ученик ID: {draft.get('student_id', '—')}\n"
        f"Тема: {draft['topic']}\n"
        "Основание: подтверждённый следующий фокус ДНК.\n\n"
        + "\n\n".join(sections)
        + "\n\nЧерновик пока не сохранён и никому не отправлен."
    )
