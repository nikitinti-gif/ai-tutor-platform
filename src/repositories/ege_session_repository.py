"""Select durable EGE storage when DATABASE_URL is configured."""

import os

from src.database.json_storage import (
    delete_ege_session as delete_json_ege_session,
    get_ege_session as get_json_ege_session,
    save_ege_session as save_json_ege_session,
)


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def _postgres_function(name: str):
    from src.database import ege_session_storage

    return getattr(ege_session_storage, name)


class EgeSessionRepository:
    @staticmethod
    def get(student_id: int):
        database_url = _database_url()
        if database_url:
            return _postgres_function("get_postgres_ege_session")(database_url, student_id)
        return get_json_ege_session(student_id)

    @staticmethod
    def save(student_id: int, attempt_data: dict, status: str = "in_progress"):
        database_url = _database_url()
        if database_url:
            return _postgres_function("save_postgres_ege_session")(
                database_url, student_id, attempt_data, status
            )
        return save_json_ege_session(student_id, attempt_data, status)

    @staticmethod
    def delete(student_id: int):
        database_url = _database_url()
        if database_url:
            return _postgres_function("delete_postgres_ege_session")(
                database_url, student_id
            )
        return delete_json_ege_session(student_id)
