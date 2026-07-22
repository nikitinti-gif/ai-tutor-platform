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
