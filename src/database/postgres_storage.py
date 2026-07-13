import json

import psycopg


SYNTHETIC_CHECKS_STATE_KEY = "synthetic_admin_checks_v1"


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
