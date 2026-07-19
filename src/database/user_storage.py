from datetime import datetime, timezone

import psycopg


VALID_USER_ROLES = {"parent", "teacher", "student"}


def _ensure_users_table(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS app_users (
            telegram_id BIGINT PRIMARY KEY,
            full_name TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT app_users_role_check CHECK (
                role IN ('parent', 'teacher', 'student')
            )
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS app_users_role_idx ON app_users (role)
        """
    )


def create_postgres_user(
    database_url: str,
    telegram_id: int,
    full_name: str,
    role: str,
) -> dict:
    if role not in VALID_USER_ROLES:
        raise ValueError("Некорректная роль пользователя.")
    now = datetime.now(timezone.utc)
    with psycopg.connect(database_url) as connection:
        _ensure_users_table(connection)
        row = connection.execute(
            """
            INSERT INTO app_users (
                telegram_id, full_name, role, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (telegram_id) DO UPDATE
            SET full_name = EXCLUDED.full_name,
                updated_at = EXCLUDED.updated_at
            RETURNING telegram_id, full_name, role, created_at
            """,
            (telegram_id, full_name, role, now, now),
        ).fetchone()
    return {
        "telegram_id": row[0],
        "full_name": row[1],
        "role": row[2],
        "created_at": row[3],
    }


def get_postgres_user(database_url: str, telegram_id: int) -> dict | None:
    with psycopg.connect(database_url) as connection:
        _ensure_users_table(connection)
        row = connection.execute(
            """
            SELECT telegram_id, full_name, role, created_at
            FROM app_users
            WHERE telegram_id = %s
            """,
            (telegram_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "telegram_id": row[0],
        "full_name": row[1],
        "role": row[2],
        "created_at": row[3],
    }


def list_postgres_users_by_role(
    database_url: str,
    role: str,
) -> list[dict]:
    if role not in VALID_USER_ROLES:
        raise ValueError("Некорректная роль пользователя.")
    with psycopg.connect(database_url) as connection:
        _ensure_users_table(connection)
        rows = connection.execute(
            """
            SELECT telegram_id, full_name, role, created_at
            FROM app_users
            WHERE role = %s
            ORDER BY created_at
            """,
            (role,),
        ).fetchall()
    return [
        {
            "telegram_id": row[0],
            "full_name": row[1],
            "role": row[2],
            "created_at": row[3],
        }
        for row in rows
    ]
