import logging
import os
from datetime import datetime, timezone

from src.database import json_storage


logger = logging.getLogger(__name__)


def persistence_info() -> dict:
    if os.getenv("DATABASE_URL", "").strip():
        return {"backend": "postgres", "durable": True}
    return {"backend": "json", "durable": False}


class EgeSessionRepository:
    """The only application access point for EGE session persistence."""

    @staticmethod
    def get(student_id: int) -> dict | None:
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            return json_storage.get_ege_session(student_id)

        from src.database.ege_session_storage import (
            get_postgres_ege_session,
            migrate_postgres_ege_session,
        )

        session = get_postgres_ege_session(database_url, student_id)
        if session is not None:
            return session
        legacy = json_storage.get_ege_session(student_id)
        if legacy is None:
            return None
        session = migrate_postgres_ege_session(database_url, student_id, legacy)
        attempt = session.get("attempt", {}) if isinstance(session, dict) else {}
        logger.info(
            "EGE_SESSION_MIGRATED student_id=%s from=json to=postgres task=%s",
            student_id,
            attempt.get("current_task", "unknown"),
        )
        return session

    @staticmethod
    def save(student_id: int, attempt_data: dict, status: str = "in_progress") -> dict:
        record = {
            "variant_id": "ege_open_2026",
            "status": status,
            "attempt": attempt_data,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            return json_storage.save_ege_session(student_id, attempt_data, status)
        from src.database.ege_session_storage import save_postgres_ege_session

        return save_postgres_ege_session(database_url, student_id, record)

    @staticmethod
    def delete(student_id: int) -> dict | None:
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            return json_storage.delete_ege_session(student_id)
        from src.database.ege_session_storage import delete_postgres_ege_session

        return delete_postgres_ege_session(database_url, student_id)
