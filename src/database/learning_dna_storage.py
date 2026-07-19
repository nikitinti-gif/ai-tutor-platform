import json
from datetime import datetime, timezone

import psycopg

from src.database.submission_storage import _ensure_submissions_table
from src.learning_dna.engine import update_learning_dna_after_check


def _ensure_learning_dna_table(connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS student_learning_dna (
            student_telegram_id BIGINT PRIMARY KEY,
            dna JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )


def get_postgres_learning_dna(
    database_url: str,
    student_telegram_id: int,
) -> dict | None:
    with psycopg.connect(database_url) as connection:
        _ensure_learning_dna_table(connection)
        row = connection.execute(
            """
            SELECT dna FROM student_learning_dna
            WHERE student_telegram_id = %s
            """,
            (student_telegram_id,),
        ).fetchone()
    return row[0] if row and isinstance(row[0], dict) else None


def save_postgres_learning_dna(
    database_url: str,
    student_telegram_id: int,
    dna: dict,
) -> dict:
    now = datetime.now(timezone.utc)
    payload = json.dumps(dna, ensure_ascii=False)
    with psycopg.connect(database_url) as connection:
        _ensure_learning_dna_table(connection)
        connection.execute(
            """
            INSERT INTO student_learning_dna (
                student_telegram_id, dna, created_at, updated_at
            ) VALUES (%s, %s::jsonb, %s, %s)
            ON CONFLICT (student_telegram_id) DO UPDATE
            SET dna = EXCLUDED.dna, updated_at = EXCLUDED.updated_at
            """,
            (student_telegram_id, payload, now, now),
        )
    return dna


def complete_submission_with_learning_dna(
    database_url: str,
    submission_id: str,
) -> dict:
    now = datetime.now(timezone.utc)
    with psycopg.connect(database_url) as connection:
        _ensure_submissions_table(connection)
        _ensure_learning_dna_table(connection)
        submission = connection.execute(
            """
            SELECT student_telegram_id, status, analysis_result
            FROM homework_submissions
            WHERE submission_id = %s
            FOR UPDATE
            """,
            (submission_id,),
        ).fetchone()

        if not submission:
            return {
                "completed": False,
                "dna_updated": False,
                "reason": "not_found",
            }

        student_id, status, analysis_result = submission
        if status == "completed":
            return {
                "completed": False,
                "dna_updated": False,
                "reason": "already_completed",
            }
        if status not in {"accepted", "teacher_review", "failed"}:
            return {
                "completed": False,
                "dna_updated": False,
                "reason": "invalid_status",
            }

        dna_updated = False
        dna_summary = None
        reason = "no_analysis"
        if student_id is None:
            reason = "student_not_linked"
        elif isinstance(analysis_result, dict):
            dna_row = connection.execute(
                """
                SELECT dna FROM student_learning_dna
                WHERE student_telegram_id = %s
                FOR UPDATE
                """,
                (student_id,),
            ).fetchone()
            current_dna = (
                dna_row[0]
                if dna_row and isinstance(dna_row[0], dict)
                else None
            )
            updated_dna = update_learning_dna_after_check(
                current_dna=current_dna,
                student_id=int(student_id),
                check_result=analysis_result,
            )
            payload = json.dumps(updated_dna, ensure_ascii=False)
            connection.execute(
                """
                INSERT INTO student_learning_dna (
                    student_telegram_id, dna, created_at, updated_at
                ) VALUES (%s, %s::jsonb, %s, %s)
                ON CONFLICT (student_telegram_id) DO UPDATE
                SET dna = EXCLUDED.dna, updated_at = EXCLUDED.updated_at
                """,
                (student_id, payload, now, now),
            )
            dna_updated = True
            trajectory = updated_dna.get("trajectory", {})
            dna_summary = {
                "signals": len(updated_dna.get("signals", [])),
                "next_focus": trajectory.get("next_focus"),
            }
            reason = "updated"

        connection.execute(
            """
            UPDATE homework_submissions
            SET status = 'completed', completed_at = %s, updated_at = %s
            WHERE submission_id = %s
            """,
            (now, now, submission_id),
        )

    return {
        "completed": True,
        "dna_updated": dna_updated,
        "reason": reason,
        "student_telegram_id": student_id,
        "dna_summary": dna_summary,
    }
