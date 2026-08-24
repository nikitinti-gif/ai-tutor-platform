import json
from datetime import datetime, timezone

import psycopg


def _ensure_table(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ege_sessions (
            student_id BIGINT PRIMARY KEY,
            session JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )


def get_postgres_ege_session(database_url: str, student_id: int) -> dict | None:
    with psycopg.connect(database_url) as connection:
        _ensure_table(connection)
        row = connection.execute(
            "SELECT session FROM ege_sessions WHERE student_id = %s",
            (student_id,),
        ).fetchone()
    return row[0] if row and isinstance(row[0], dict) else None


def save_postgres_ege_session(
    database_url: str, student_id: int, session: dict
) -> dict:
    with psycopg.connect(database_url) as connection:
        _ensure_table(connection)
        connection.execute(
            """
            INSERT INTO ege_sessions (student_id, session, updated_at)
            VALUES (%s, %s::jsonb, %s)
            ON CONFLICT (student_id) DO UPDATE
            SET session = EXCLUDED.session, updated_at = EXCLUDED.updated_at
            """,
            (student_id, json.dumps(session, ensure_ascii=False), datetime.now(timezone.utc)),
        )
    return session


def migrate_postgres_ege_session(
    database_url: str, student_id: int, session: dict
) -> dict:
    """Insert legacy data only while PostgreSQL has no source-of-truth row."""
    with psycopg.connect(database_url) as connection:
        _ensure_table(connection)
        connection.execute(
            """
            INSERT INTO ege_sessions (student_id, session, updated_at)
            VALUES (%s, %s::jsonb, %s)
            ON CONFLICT (student_id) DO NOTHING
            """,
            (student_id, json.dumps(session, ensure_ascii=False), datetime.now(timezone.utc)),
        )
        row = connection.execute(
            "SELECT session FROM ege_sessions WHERE student_id = %s",
            (student_id,),
        ).fetchone()
    return row[0]


def delete_postgres_ege_session(database_url: str, student_id: int) -> dict | None:
    with psycopg.connect(database_url) as connection:
        _ensure_table(connection)
        row = connection.execute(
            "DELETE FROM ege_sessions WHERE student_id = %s RETURNING session",
            (student_id,),
        ).fetchone()
    return row[0] if row else None
