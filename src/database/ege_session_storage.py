"""PostgreSQL storage for restart-safe EGE exam sessions."""

import json
from datetime import datetime, timezone

import psycopg


def _ensure_ege_sessions_table(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ege_sessions (
            student_telegram_id BIGINT PRIMARY KEY,
            variant_id TEXT NOT NULL,
            status TEXT NOT NULL,
            attempt JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )


def get_postgres_ege_session(database_url: str, student_id: int) -> dict | None:
    with psycopg.connect(database_url) as connection:
        _ensure_ege_sessions_table(connection)
        row = connection.execute(
            """SELECT variant_id, status, attempt, updated_at
               FROM ege_sessions WHERE student_telegram_id = %s""",
            (student_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "variant_id": row[0],
        "status": row[1],
        "attempt": row[2],
        "updated_at": row[3].isoformat() if hasattr(row[3], "isoformat") else row[3],
    }


def save_postgres_ege_session(
    database_url: str, student_id: int, attempt_data: dict, status: str = "in_progress"
) -> dict:
    now = datetime.now(timezone.utc)
    variant_id = "ege_open_2026"
    with psycopg.connect(database_url) as connection:
        _ensure_ege_sessions_table(connection)
        connection.execute(
            """
            INSERT INTO ege_sessions (
                student_telegram_id, variant_id, status, attempt, created_at, updated_at
            ) VALUES (%s, %s, %s, %s::jsonb, %s, %s)
            ON CONFLICT (student_telegram_id) DO UPDATE SET
                variant_id = EXCLUDED.variant_id,
                status = EXCLUDED.status,
                attempt = EXCLUDED.attempt,
                updated_at = EXCLUDED.updated_at
            """,
            (student_id, variant_id, status, json.dumps(attempt_data, ensure_ascii=False), now, now),
        )
    return {
        "variant_id": variant_id,
        "status": status,
        "attempt": attempt_data,
        "updated_at": now.isoformat(),
    }


def delete_postgres_ege_session(database_url: str, student_id: int) -> bool:
    with psycopg.connect(database_url) as connection:
        _ensure_ege_sessions_table(connection)
        result = connection.execute(
            "DELETE FROM ege_sessions WHERE student_telegram_id = %s", (student_id,)
        )
    return result.rowcount > 0
