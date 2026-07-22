from datetime import datetime
from uuid import uuid4


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
        "purpose": (
            "Проверить понимание соответствия двоичных разрядов степеням "
            "двойки и умение находить пропущенный вес."
        ),
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


ARITHMETIC_IN_NUMERATION_SYSTEMS_TASKS = [
    {
        "level": "Лёгкий",
        "task": (
            "Выполни сложение в двоичной системе: 1011₂ + 0110₂. "
            "Запиши вычисление столбиком и результат в двоичной системе."
        ),
        "teacher_answer": "1011₂ + 0110₂ = 10001₂ (11 + 6 = 17).",
        "purpose": (
            "Проверить базовое сложение двоичных разрядов и перенос единицы "
            "в следующий разряд."
        ),
    },
    {
        "level": "Средний",
        "task": (
            "Ученик записал: 11010₂ − 01011₂ = 10001₂. Найди ошибку, "
            "выполни вычитание правильно и проверь результат в десятичной системе."
        ),
        "teacher_answer": (
            "11010₂ − 01011₂ = 01111₂; проверка: 26 − 11 = 15. "
            "Запись 10001₂ равна 17 и не проходит проверку."
        ),
        "purpose": (
            "Проверить вычитание с заимствованием, обнаружение ошибки и "
            "самопроверку переводом в десятичную систему."
        ),
    },
    {
        "level": "Сложный",
        "task": (
            "Вычисли 1011₂ × 101₂ без предварительного перевода множителей "
            "в десятичную систему. Покажи промежуточные строки двоичного "
            "умножения, затем проверь итог переводом в десятичную систему."
        ),
        "teacher_answer": (
            "1011₂ × 101₂ = 1011₂ + 101100₂ = 110111₂; "
            "проверка: 11 × 5 = 55."
        ),
        "purpose": (
            "Проверить перенос разрядных алгоритмов на двоичное умножение "
            "и независимую проверку результата."
        ),
    },
]


VERIFIED_TASK_TEMPLATES = {
    "Системы счисления": SYSTEMS_OF_NUMERATION_TASKS,
    "Арифметические операции в системах счисления": (
        ARITHMETIC_IN_NUMERATION_SYSTEMS_TASKS
    ),
}


def build_adaptive_task_draft(dna: dict) -> dict:
    topic = (dna.get("trajectory") or {}).get("next_focus")
    tasks = VERIFIED_TASK_TEMPLATES.get(topic)
    if tasks is None:
        raise ValueError("Для этой темы пока нет проверенного шаблона заданий.")

    return {
        "student_id": dna.get("student_id"),
        "topic": topic,
        "tasks": [dict(task) for task in tasks],
        "status": "teacher_draft",
        "created_by": "verified_adaptive_template_v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "draft_token": uuid4().hex[:16],
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


def format_adaptive_task_set_for_family(task_set: dict) -> str:
    sections = []
    for index, task in enumerate(task_set["tasks"], start=1):
        sections.append(
            f"{index}. {task['level']} уровень\n"
            f"Задание: {task['task']}"
        )
    return (
        "📝 Диагностические задания\n\n"
        f"Тема: {task_set['topic']}\n"
        "Выполните все три задания и отправьте фотографию решения.\n\n"
        + "\n\n".join(sections)
        + f"\n\nНомер набора: {task_set['task_set_id']}"
    )
