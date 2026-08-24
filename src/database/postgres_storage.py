import json

import psycopg


SYNTHETIC_CHECKS_STATE_KEY = "synthetic_admin_checks_v1"
EGE_SESSION_STATE_KEY_PREFIX = "ege_session_v1:"


def _ensure_state_table(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS app_state (
            state_key TEXT PRIMARY KEY,
            state_value JSONB NOT NULL
        )
        """
    )


def append_synthetic_learning_check(database_url: str, record: dict):
    payload = json.dumps([record], ensure_ascii=False)

    with psycopg.connect(database_url) as connection:
        _ensure_state_table(connection)
        connection.execute(
            """
            INSERT INTO app_state (state_key, state_value)
            VALUES (%s, %s::jsonb)
            ON CONFLICT (state_key) DO UPDATE
            SET state_value = app_state.state_value || EXCLUDED.state_value
            """,
            (SYNTHETIC_CHECKS_STATE_KEY, payload),
        )

    return record


def load_synthetic_learning_checks(database_url: str):
    with psycopg.connect(database_url) as connection:
        _ensure_state_table(connection)
        row = connection.execute(
            "SELECT state_value FROM app_state WHERE state_key = %s",
            (SYNTHETIC_CHECKS_STATE_KEY,),
        ).fetchone()

    if not row or not isinstance(row[0], list):
        return []

    return row[0]


def load_ege_session(database_url: str, student_id: int):
    """Load one exam session from the existing durable app_state table."""
    with psycopg.connect(database_url) as connection:
        _ensure_state_table(connection)
        row = connection.execute(
            "SELECT state_value FROM app_state WHERE state_key = %s",
            (f"{EGE_SESSION_STATE_KEY_PREFIX}{student_id}",),
        ).fetchone()
    return row[0] if row and isinstance(row[0], dict) else None


def save_ege_session(database_url: str, student_id: int, record: dict):
    """Upsert one complete session snapshot atomically."""
    with psycopg.connect(database_url) as connection:
        _ensure_state_table(connection)
        connection.execute(
            """
            INSERT INTO app_state (state_key, state_value)
            VALUES (%s, %s::jsonb)
            ON CONFLICT (state_key) DO UPDATE
            SET state_value = EXCLUDED.state_value
            """,
            (
                f"{EGE_SESSION_STATE_KEY_PREFIX}{student_id}",
                json.dumps(record, ensure_ascii=False),
            ),
        )
    return record


def delete_ege_session(database_url: str, student_id: int):
    """Delete and return a session, matching the local JSON contract."""
    with psycopg.connect(database_url) as connection:
        _ensure_state_table(connection)
        row = connection.execute(
            "DELETE FROM app_state WHERE state_key = %s RETURNING state_value",
            (f"{EGE_SESSION_STATE_KEY_PREFIX}{student_id}",),
        ).fetchone()
    return row[0] if row else None
