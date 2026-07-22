import json
from datetime import datetime, timezone

import psycopg


def _ensure_adaptive_task_sets_table(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS adaptive_task_sets (
            task_set_id TEXT PRIMARY KEY,
            draft_token TEXT NOT NULL UNIQUE,
            student_telegram_id BIGINT NOT NULL,
            teacher_telegram_id BIGINT NOT NULL,
            topic TEXT NOT NULL,
            tasks JSONB NOT NULL,
            status TEXT NOT NULL,
            source TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            confirmed_at TIMESTAMPTZ NOT NULL
        )
        """
    )
    connection.execute(
        "ALTER TABLE adaptive_task_sets ADD COLUMN IF NOT EXISTS sent_at TIMESTAMPTZ"
    )
    connection.execute(
        "ALTER TABLE adaptive_task_sets ADD COLUMN IF NOT EXISTS sent_to_parent_id BIGINT"
    )


def save_postgres_adaptive_task_set(
    database_url: str,
    draft: dict,
    teacher_telegram_id: int,
) -> dict:
    token = str(draft["draft_token"])
    task_set_id = f"diag_{token}"
    now = datetime.now(timezone.utc)
    with psycopg.connect(database_url) as connection:
        _ensure_adaptive_task_sets_table(connection)
        row = connection.execute(
            """
            INSERT INTO adaptive_task_sets (
                task_set_id, draft_token, student_telegram_id,
                teacher_telegram_id, topic, tasks, status, source,
                created_at, confirmed_at
            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, 'confirmed', %s, %s, %s)
            ON CONFLICT (draft_token) DO UPDATE
            SET draft_token = EXCLUDED.draft_token
            RETURNING task_set_id, status
            """,
            (
                task_set_id,
                token,
                int(draft["student_id"]),
                int(teacher_telegram_id),
                draft["topic"],
                json.dumps(draft["tasks"], ensure_ascii=False),
                draft["created_by"],
                now,
                now,
            ),
        ).fetchone()
    return {
        "task_set_id": row[0],
        "status": row[1],
        "student_id": int(draft["student_id"]),
        "topic": draft["topic"],
    }


def get_postgres_adaptive_task_set(database_url: str, task_set_id: str) -> dict | None:
    with psycopg.connect(database_url) as connection:
        _ensure_adaptive_task_sets_table(connection)
        row = connection.execute(
            """
            SELECT task_set_id, student_telegram_id, teacher_telegram_id,
                   topic, tasks, status, sent_at, sent_to_parent_id
            FROM adaptive_task_sets WHERE task_set_id = %s
            """,
            (task_set_id,),
        ).fetchone()
    if not row:
        return None
    return {
        "task_set_id": row[0], "student_id": int(row[1]),
        "teacher_id": int(row[2]), "topic": row[3], "tasks": row[4],
        "status": row[5], "sent_at": row[6], "parent_id": row[7],
    }


def mark_postgres_adaptive_task_set_sent(
    database_url: str, task_set_id: str, parent_telegram_id: int
) -> bool:
    now = datetime.now(timezone.utc)
    with psycopg.connect(database_url) as connection:
        _ensure_adaptive_task_sets_table(connection)
        row = connection.execute(
            """
            UPDATE adaptive_task_sets
            SET status = 'sent', sent_at = %s, sent_to_parent_id = %s
            WHERE task_set_id = %s AND status = 'confirmed'
            RETURNING task_set_id
            """,
            (now, parent_telegram_id, task_set_id),
        ).fetchone()
    return row is not None
