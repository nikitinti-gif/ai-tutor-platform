from datetime import datetime, timedelta, timezone

import psycopg


def _ensure_family_link_tables(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS parent_student_links (
            parent_telegram_id BIGINT PRIMARY KEY,
            student_telegram_id BIGINT NOT NULL,
            linked_by_teacher_id BIGINT NOT NULL,
            linked_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS parent_link_codes (
            code_hash TEXT PRIMARY KEY,
            student_telegram_id BIGINT NOT NULL,
            teacher_telegram_id BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            used_at TIMESTAMPTZ
        )
        """
    )


def save_parent_link_code(
    database_url: str,
    code_hash: str,
    student_telegram_id: int,
    teacher_telegram_id: int,
    lifetime_minutes: int = 30,
) -> None:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=lifetime_minutes)
    with psycopg.connect(database_url) as connection:
        _ensure_family_link_tables(connection)
        connection.execute(
            """
            INSERT INTO parent_link_codes (
                code_hash, student_telegram_id, teacher_telegram_id,
                created_at, expires_at
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (
                code_hash,
                student_telegram_id,
                teacher_telegram_id,
                now,
                expires_at,
            ),
        )


def consume_parent_link_code(
    database_url: str,
    code_hash: str,
    parent_telegram_id: int,
) -> int | None:
    now = datetime.now(timezone.utc)
    with psycopg.connect(database_url) as connection:
        _ensure_family_link_tables(connection)
        row = connection.execute(
            """
            SELECT student_telegram_id, teacher_telegram_id
            FROM parent_link_codes
            WHERE code_hash = %s
              AND used_at IS NULL
              AND expires_at > %s
            FOR UPDATE
            """,
            (code_hash, now),
        ).fetchone()
        if not row:
            return None

        student_telegram_id, teacher_telegram_id = row
        connection.execute(
            """
            INSERT INTO parent_student_links (
                parent_telegram_id, student_telegram_id,
                linked_by_teacher_id, linked_at
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (parent_telegram_id) DO UPDATE
            SET student_telegram_id = EXCLUDED.student_telegram_id,
                linked_by_teacher_id = EXCLUDED.linked_by_teacher_id,
                linked_at = EXCLUDED.linked_at
            """,
            (
                parent_telegram_id,
                student_telegram_id,
                teacher_telegram_id,
                now,
            ),
        )
        connection.execute(
            """
            UPDATE parent_link_codes SET used_at = %s WHERE code_hash = %s
            """,
            (now, code_hash),
        )
    return int(student_telegram_id)


def get_linked_student_id(
    database_url: str,
    parent_telegram_id: int,
) -> int | None:
    with psycopg.connect(database_url) as connection:
        _ensure_family_link_tables(connection)
        row = connection.execute(
            """
            SELECT student_telegram_id
            FROM parent_student_links
            WHERE parent_telegram_id = %s
            """,
            (parent_telegram_id,),
        ).fetchone()
    return int(row[0]) if row else None
