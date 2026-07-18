import json
from datetime import datetime, timezone

import psycopg


SUBMISSION_STATUSES = {
    "accepted",
    "processing",
    "teacher_review",
    "completed",
    "failed",
}


def _ensure_submissions_table(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS homework_submissions (
            submission_id TEXT PRIMARY KEY,
            parent_telegram_id BIGINT NOT NULL,
            student_telegram_id BIGINT,
            is_synthetic BOOLEAN NOT NULL DEFAULT FALSE,
            telegram_file_id TEXT NOT NULL,
            telegram_file_unique_id TEXT NOT NULL,
            status TEXT NOT NULL,
            photo_width INTEGER NOT NULL,
            photo_height INTEGER NOT NULL,
            quality_metrics JSONB NOT NULL,
            processing_attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at TIMESTAMPTZ NOT NULL,
            teacher_notified_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT homework_submissions_status_check CHECK (
                status IN (
                    'accepted', 'processing', 'teacher_review',
                    'completed', 'failed'
                )
            )
        )
        """
    )
    connection.execute(
        """
        ALTER TABLE homework_submissions
        ADD COLUMN IF NOT EXISTS is_synthetic BOOLEAN NOT NULL DEFAULT FALSE
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS homework_submissions_status_created_idx
        ON homework_submissions (status, created_at)
        """
    )


def create_homework_submission(database_url: str, submission: dict) -> dict:
    status = submission.get("status", "accepted")
    if status not in SUBMISSION_STATUSES:
        raise ValueError("Некорректный статус принятой работы.")

    now = datetime.now(timezone.utc)
    record = {
        **submission,
        "status": status,
        "created_at": now,
        "updated_at": now,
    }
    quality_metrics = json.dumps(
        record["quality_metrics"],
        ensure_ascii=False,
    )

    with psycopg.connect(database_url) as connection:
        _ensure_submissions_table(connection)
        connection.execute(
            """
            INSERT INTO homework_submissions (
                submission_id,
                parent_telegram_id,
                student_telegram_id,
                is_synthetic,
                telegram_file_id,
                telegram_file_unique_id,
                status,
                photo_width,
                photo_height,
                quality_metrics,
                created_at,
                updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s
            )
            """,
            (
                record["submission_id"],
                record["parent_telegram_id"],
                record.get("student_telegram_id"),
                bool(record.get("is_synthetic", False)),
                record["telegram_file_id"],
                record["telegram_file_unique_id"],
                record["status"],
                record["photo_width"],
                record["photo_height"],
                quality_metrics,
                record["created_at"],
                record["updated_at"],
            ),
        )

    return record


def mark_teacher_notified(database_url: str, submission_id: str) -> None:
    now = datetime.now(timezone.utc)
    with psycopg.connect(database_url) as connection:
        _ensure_submissions_table(connection)
        connection.execute(
            """
            UPDATE homework_submissions
            SET teacher_notified_at = %s, updated_at = %s
            WHERE submission_id = %s
            """,
            (now, now, submission_id),
        )
