import json
import os
from datetime import datetime
from uuid import uuid4

DB_FILE = "database.json"


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
