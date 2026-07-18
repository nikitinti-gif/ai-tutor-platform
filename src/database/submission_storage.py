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
            analysis_result JSONB,
            processing_attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at TIMESTAMPTZ NOT NULL,
            teacher_notified_at TIMESTAMPTZ,
            analysis_notified_at TIMESTAMPTZ,
            processed_at TIMESTAMPTZ,
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
        ALTER TABLE homework_submissions
        ADD COLUMN IF NOT EXISTS analysis_result JSONB
        """
    )
    connection.execute(
        """
        ALTER TABLE homework_submissions
        ADD COLUMN IF NOT EXISTS analysis_notified_at TIMESTAMPTZ
        """
    )
    connection.execute(
        """
        ALTER TABLE homework_submissions
        ADD COLUMN IF NOT EXISTS processed_at TIMESTAMPTZ
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


def claim_next_synthetic_submission(
    database_url: str,
    max_attempts: int,
) -> dict | None:
    now = datetime.now(timezone.utc)
    with psycopg.connect(database_url) as connection:
        _ensure_submissions_table(connection)
        row = connection.execute(
            """
            WITH candidate AS (
                SELECT submission_id
                FROM homework_submissions
                WHERE status = 'accepted'
                  AND is_synthetic = TRUE
                  AND processing_attempts < %s
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE homework_submissions AS submission
            SET status = 'processing',
                processing_attempts = processing_attempts + 1,
                last_error = NULL,
                updated_at = %s
            FROM candidate
            WHERE submission.submission_id = candidate.submission_id
            RETURNING
                submission.submission_id,
                submission.student_telegram_id,
                submission.telegram_file_id,
                submission.processing_attempts
            """,
            (max_attempts, now),
        ).fetchone()
    if not row:
        return None
    return {
        "submission_id": row[0],
        "student_telegram_id": row[1],
        "telegram_file_id": row[2],
        "processing_attempts": row[3],
    }


def save_submission_analysis(
    database_url: str,
    submission_id: str,
    analysis_result: dict,
) -> None:
    now = datetime.now(timezone.utc)
    payload = json.dumps(analysis_result, ensure_ascii=False)
    with psycopg.connect(database_url) as connection:
        _ensure_submissions_table(connection)
        connection.execute(
            """
            UPDATE homework_submissions
            SET status = 'teacher_review',
                analysis_result = %s::jsonb,
                processed_at = %s,
                updated_at = %s,
                last_error = NULL
            WHERE submission_id = %s AND is_synthetic = TRUE
            """,
            (payload, now, now, submission_id),
        )


def release_or_fail_submission(
    database_url: str,
    submission_id: str,
    error_message: str,
    max_attempts: int,
) -> None:
    now = datetime.now(timezone.utc)
    with psycopg.connect(database_url) as connection:
        _ensure_submissions_table(connection)
        connection.execute(
            """
            UPDATE homework_submissions
            SET status = CASE
                    WHEN processing_attempts >= %s THEN 'failed'
                    ELSE 'accepted'
                END,
                last_error = %s,
                updated_at = %s
            WHERE submission_id = %s
              AND status = 'processing'
              AND is_synthetic = TRUE
            """,
            (max_attempts, error_message[:1000], now, submission_id),
        )


def get_pending_analysis_notification(database_url: str) -> dict | None:
    with psycopg.connect(database_url) as connection:
        _ensure_submissions_table(connection)
        row = connection.execute(
            """
            SELECT submission_id, analysis_result
            FROM homework_submissions
            WHERE status = 'teacher_review'
              AND is_synthetic = TRUE
              AND analysis_result IS NOT NULL
              AND analysis_notified_at IS NULL
            ORDER BY processed_at
            LIMIT 1
            """
        ).fetchone()
    if not row:
        return None
    return {"submission_id": row[0], "analysis_result": row[1]}


def mark_analysis_notified(database_url: str, submission_id: str) -> None:
    now = datetime.now(timezone.utc)
    with psycopg.connect(database_url) as connection:
        _ensure_submissions_table(connection)
        connection.execute(
            """
            UPDATE homework_submissions
            SET analysis_notified_at = %s, updated_at = %s
            WHERE submission_id = %s AND is_synthetic = TRUE
            """,
            (now, now, submission_id),
        )
