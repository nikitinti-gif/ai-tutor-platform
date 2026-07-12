from datetime import datetime
from uuid import uuid4

from src.database.json_storage import load_db, save_db


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_list(db: dict, key: str):
    if key not in db or not isinstance(db[key], list):
        db[key] = []


def _ensure_dict(db: dict, key: str):
    if key not in db or not isinstance(db[key], dict):
        db[key] = {}


def create_informatics_demo(user_id: int, full_name: str) -> str:
    db = load_db()

    _ensure_list(db, "users")
    _ensure_list(db, "homework")
    _ensure_list(db, "student_homework")
    _ensure_dict(db, "learning_dna")
    _ensure_list(db, "pedagogical_decisions")

    # 1. Demo student
    existing_user = None

    for user in db["users"]:
        if str(user.get("telegram_id")) == str(user_id):
            existing_user = user
            break

    if existing_user:
        existing_user["role"] = "student"
        existing_user["full_name"] = full_name
        existing_user["subject"] = "Информатика"
    else:
        db["users"].append(
            {
                "telegram_id": user_id,
                "full_name": full_name,
                "role": "student",
                "subject": "Информатика",
                "created_at": _now(),
            }
        )

    # 2. Homework
    homework_id = str(uuid4())

    homework_data = {
        "topic": "Информатика: условные операторы",
        "theory": (
            "Условный оператор позволяет программе выполнять разные действия "
            "в зависимости от истинности условия."
        ),
        "tasks": [
            {
                "number": 1,
                "text": (
                    "Дано число x. Если x больше 10, вывести 'Да', "
                    "иначе вывести 'Нет'."
                ),
            },
            {
                "number": 2,
                "text": (
                    "Объясни, какая ветка выполнится при x = 7 "
                    "и почему."
                ),
            },
        ],
        "difficulty": "basic",
        "estimated_time_minutes": 15,
        "created_by": "demo_mode",
        "created_at": _now(),
    }

    db["homework"].append(
        {
            "homework_id": homework_id,
            "topic": "Информатика: условные операторы",
            "homework_data": homework_data,
            "created_at": _now(),
        }
    )

    # 3. Checked assignment
    student_homework_id = str(uuid4())

    db["student_homework"].append(
        {
            "student_homework_id": student_homework_id,
            "homework_id": homework_id,
            "student_id": user_id,
            "status": "checked",
            "assigned_at": _now(),
            "opened_at": _now(),
            "submitted_at": _now(),
            "checked_at": _now(),
            "last_error_type": "logic_condition_error",
            "teacher_review_required": False,
        }
    )

    # 4. Learning DNA
    db["learning_dna"][str(user_id)] = {
        "student_id": user_id,
        "identity": {
            "exam": "ОГЭ",
            "subject": "Информатика",
            "target_score": None,
        },
        "skills": {
            "conditional_logic": {
                "skill_id": "conditional_logic",
                "skill_level": 42,
                "skill_confidence": 35,
                "attempts": 3,
                "successes": 1,
                "mistakes": 2,
                "trend": "down",
            },
            "algorithm_explanation": {
                "skill_id": "algorithm_explanation",
                "skill_level": 55,
                "skill_confidence": 40,
                "attempts": 2,
                "successes": 2,
                "mistakes": 0,
                "trend": "up",
            },
        },
        "signals": [
            {
                "type": "mistake",
                "topic": "Информатика",
                "skill_id": "conditional_logic",
                "error_type": "logic_condition_error",
                "created_at": _now(),
            }
        ],
        "memory": {
            "last_topics": [
                "Информатика: условные операторы"
            ],
            "last_errors": [
                {
                    "topic": "Информатика",
                    "skill_id": "conditional_logic",
                    "error_type": "logic_condition_error",
                }
            ],
            "last_successes": [
                {
                    "topic": "Объяснение алгоритма",
                    "skill_id": "algorithm_explanation",
                }
            ],
        },
        "motivation": {
            "xp": 50,
            "streak_days": 1,
        },
        "trajectory": {
            "next_focus": "Условные операторы",
            "recommendations": [
                "Повторить правила работы if/else.",
                "Решить 3 задачи на выбор правильной ветки условия.",
            ],
        },
        "predictions": {
            "estimated_score": None,
        },
        "ai_notes": [
            "Ученик путает условие и противоположную ветку else."
        ],
        "created_at": _now(),
        "updated_at": _now(),
    }

    # 5. Pedagogical decision
    db["pedagogical_decisions"].append(
        {
            "student_id": user_id,
            "created_at": _now(),
            "observation": {
                "topic": "Информатика",
                "status": "has_error",
                "error_type": "logic_condition_error",
            },
            "evidence": [
                "В решении неверно выбрана ветка условного оператора.",
                "Ошибка связана с пониманием условия if/else.",
            ],
            "reasoning": (
                "Если ученик путает условие и ветку else, значит навык "
                "условной логики пока закреплён недостаточно."
            ),
            "decision": {
                "type": "targeted_practice",
                "focus": "conditional_logic",
            },
            "action_plan": [
                "Повторить правило работы условного оператора.",
                "Решить 3 короткие задачи на if/else.",
                "Через 2 дня дать контрольную задачу на эту же тему.",
            ],
        }
    )

    save_db(db)

    return (
        "✅ Demo Mode создан.\n\n"
        "Предмет: Информатика\n"
        "Тема: Условные операторы\n"
        "Статус: решение проверено\n\n"
        "Теперь нажми кнопку родительского отчёта."
    )