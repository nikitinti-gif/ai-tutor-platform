import json
import os
from datetime import datetime
from uuid import uuid4

DB_FILE = "database.json"
SYNTHETIC_CHECKS_KEY = "_synthetic_admin_checks"
SYNTHETIC_CHECK_FIELDS = {
    "topic",
    "status",
    "confidence",
    "error_type",
}
SYNTHETIC_CHECK_STATUSES = {
    "correct",
    "has_error",
    "unclear",
}


def load_db():
    if not os.path.exists(DB_FILE):
        return {
            "users": [],
            "homework": [],
            "learning_dna": {},
            "pedagogical_decisions": [],
            "student_homework": [],
        }

    with open(DB_FILE, "r", encoding="utf-8") as file:
        db = json.load(file)

    db.setdefault("users", [])
    db.setdefault("homework", [])
    db.setdefault("learning_dna", {})
    db.setdefault("pedagogical_decisions", [])
    db.setdefault("student_homework", [])
    return db


def save_db(data):
    with open(DB_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def get_user_by_telegram_id(telegram_id: int):
    db = load_db()

    for user in db["users"]:
        if user["telegram_id"] == telegram_id:
            return user

    return None


def create_user(telegram_id: int, full_name: str, role: str):
    db = load_db()

    user = {
        "telegram_id": telegram_id,
        "full_name": full_name,
        "role": role,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    db["users"].append(user)
    save_db(db)

    return user


def get_users_by_role(role: str):
    db = load_db()

    return [
        user for user in db["users"]
        if user["role"] == role
    ]


def create_homework(topic: str, homework_data: dict, teacher_id: int):
    db = load_db()

    homework = {
        "homework_id": str(uuid4()),
        "topic": topic,
        "homework_data": homework_data,
        "teacher_id": teacher_id,
        "status": "active",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    db["homework"].append(homework)
    save_db(db)

    return homework


def get_active_homework():
    db = load_db()

    return [
        item for item in db["homework"]
        if item.get("status") == "active"
    ]

def get_learning_dna(student_id: int):
    db = load_db()
    return db["learning_dna"].get(str(student_id))


def save_learning_dna(student_id: int, dna: dict):
    db = load_db()
    db["learning_dna"][str(student_id)] = dna
    save_db(db)
    return dna


def save_synthetic_learning_check(check_result: dict):
    status = check_result.get("status")
    if status not in SYNTHETIC_CHECK_STATUSES:
        raise ValueError("Некорректный статус синтетической проверки.")

    try:
        confidence = float(check_result.get("confidence", 0.0))
    except (TypeError, ValueError) as error:
        raise ValueError("Некорректная уверенность проверки.") from error

    topic = check_result.get("topic")
    error_type = check_result.get("error_type")
    record = {
        "topic": topic if isinstance(topic, str) and topic else "unknown",
        "status": status,
        "confidence": max(0.0, min(confidence, 1.0)),
        "error_type": (
            error_type
            if isinstance(error_type, str) and error_type
            else None
        ),
    }

    if set(record) != SYNTHETIC_CHECK_FIELDS:
        raise RuntimeError("Нарушен контракт политики хранения v1.")

    db = load_db()
    checks = db["learning_dna"].setdefault(SYNTHETIC_CHECKS_KEY, [])
    if not isinstance(checks, list):
        raise ValueError("Повреждён журнал синтетических проверок.")

    checks.append(record)
    save_db(db)
    return record


def get_synthetic_learning_checks():
    db = load_db()
    checks = db["learning_dna"].get(SYNTHETIC_CHECKS_KEY, [])
    return checks if isinstance(checks, list) else []

def save_pedagogical_decision(student_id: int, decision_data: dict):
    db = load_db()

    record = {
        "student_id": student_id,
        "decision_data": decision_data,
    }

    db["pedagogical_decisions"].append(record)
    save_db(db)

    return record

def create_student_homework(homework_id: str, student_id: int):
    db = load_db()

    record = {
        "student_homework_id": str(uuid4()),
        "homework_id": homework_id,
        "student_id": student_id,
        "status": "new",
        "assigned_at": datetime.now().isoformat(timespec="seconds"),
        "submitted_at": None,
        "checked_at": None,
        "last_error_type": None,
        "teacher_review_required": False,
    }

    db["student_homework"].append(record)
    save_db(db)

    return record


def get_student_homework_by_student_id(student_id: int):
    db = load_db()

    return [
        item for item in db["student_homework"]
        if item["student_id"] == student_id
    ]

def update_student_homework_status(
    student_homework_id: str,
    status: str,
    extra_fields: dict | None = None,
):
    db = load_db()

    for item in db["student_homework"]:
        if item["student_homework_id"] == student_homework_id:
            item["status"] = status

            if extra_fields:
                item.update(extra_fields)

            save_db(db)
            return item

    return None


def get_latest_student_homework(student_id: int):
    db = load_db()

    student_items = [
        item for item in db["student_homework"]
        if item["student_id"] == student_id
    ]

    if not student_items:
        return None

    return student_items[-1]
